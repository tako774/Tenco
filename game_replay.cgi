#!/usr/bin/ruby

### リプレイファイル一覧ページ出力

# 開始時刻
begin
  now = Time.now
  # リビジョン
  REVISION = 'R0.02'
  DEBUG = false

  $LOAD_PATH.unshift './common'
  $LOAD_PATH.unshift './entity'
  $LOAD_PATH.unshift './dao'

  require 'time'
  require 'logger'
  require 'segment_const'
  require 'utils'
  require 'setting'
  require 'html_helper'

  # 設定読み込み
  CFG = Setting.new
  # TOP ページ URL
  TOP_URL = CFG['top_url']
  # TOP ディレクトリパス
  TOP_DIR = '.'
  # ログファイルパス
  LOG_PATH = "#{TOP_DIR}/log/log_#{now.strftime('%Y%m%d')}.log"
  ACCESS_LOG_PATH = "#{TOP_DIR}/log/access_#{now.strftime('%Y%m%d')}.log"
  ERROR_LOG_PATH = "#{TOP_DIR}/log/error_#{now.strftime('%Y%m%d')}.log"
  
  # キャッシュの有効期限
  cache_expires = (now + 60 * 60) - now.min * 60 - now.sec
  # キャッシュ親パス
  CACHE_BASE="./cache/#{cache_expires.strftime('%Y%m%d%H%M%S')}"
  # キャッシュフォルダパス
  CACHE_DIR = "#{CACHE_BASE}/#{File::basename(__FILE__)}"
  # キャッシュロックフォルダパス
  CACHE_LOCK_DIR = "#{CACHE_BASE}/lock_#{File::basename(__FILE__)}"
  # キャッシュをつかったかどうか
  is_cache_used = false

  # HTTP/HTTPSレスポンス文字列
  res_status = "Status: 500 Server Error\n"
  res_header = "content-type:text/plain; charset=utf-8\n"
  res_body = ""

  # ログ開始
  logger = Logger.new(LOG_PATH)
  logger.level = Logger::DEBUG

  # アクセスログ記録
  access_logger = Logger.new(ACCESS_LOG_PATH)
  access_logger.level = Logger::DEBUG
  access_logger.info(
    [
      "",
      now.strftime('%Y/%m/%d %H:%M:%S'),
      ENV['HTTP_X_FORWARDED_FOR'] || ENV['HTTP_X_REAL_IP'] || ENV['REMOTE_ADDR'],
      ENV['HTTP_USER_AGENT'],
      ENV['REQUEST_URI'],
      File::basename(__FILE__)
    ].join("\t")
  )
  

rescue
  print "Status: 500 Internal Server Error\n"
  print "content-type: text/plain\n\n"
  print "サーバーエラーです。ごめんなさい。(Initialize Error #{Time.now.strftime('%Y/%m/%d %H:%m:%S')})"
  exit
end

if ENV['REQUEST_METHOD'] == 'GET' then
  begin
    query = {} # クエリストリング
    db = nil   # DB接続 

    LINK_INTERNAL_ERB_PATH = "./link_internal.erb" # 内部リンクERBパス
    LINK_ERB_PATH   = "./link.erb"   # リンクERBパス
    FOOTER_ERB_PATH = "./footer.erb" # フッターERBパス
    
    replays = [] # リプレイ情報
    track_records = {} # track_record_id => track_record
        
    # クエリストリング分解
    query = parse_query_str(ENV['QUERY_STRING'])
    
    # バリデーション
    unless query['game_id'] && query['game_id'] =~ /\A[1-9][0-9]*\z/ then
      res_status = "Status: 404 Not Found.\n"
      res_status = "Location: /404\n"
      raise "存在しないゲームIDが指定されました。(#{query['game_id']})"
    end
    
    game_id = query['game_id'].to_i       # ゲーム番号
    
    # キャッシュフォルダがなければ生成
    Dir.mkdir(CACHE_BASE, 0700) unless File.exist?(CACHE_BASE)
    Dir.mkdir(CACHE_DIR, 0700) unless File.exist?(CACHE_DIR)
    Dir.mkdir(CACHE_LOCK_DIR, 0700) unless File.exist?(CACHE_LOCK_DIR)

    # キャッシュパス設定・プロセスロックファイルパス設定
    cache_html_path = "#{CACHE_DIR}/#{File::basename(__FILE__)}_#{game_id.to_i}.html"
    cache_html_header_path = "#{cache_html_path}.h"
    cache_lock_path = "#{CACHE_LOCK_DIR}/#{File::basename(__FILE__)}_#{game_id.to_i}lock"
    
    # キャッシュパスのバリデーション
    if cache_html_path =~ /\.{2}/ or cache_lock_path =~ /\.{2}/ then
      raise "ディレクトリトラバーサルの疑いがあります"
    end
    
    # デバッグ時か、キャッシュが無いかあってもサイズ0か、
    # ロックファイルが無いか、（＝キャッシュの再生成を行う条件）、キャッシュ生成
    unless (!DEBUG and
      File.exist?(cache_html_path) and (File.size(cache_html_path) != 0) and
      File.exist?(cache_html_header_path) and (File.size(cache_html_header_path) != 0) and
      File.exist?(cache_lock_path)
    ) then
      ### キャッシュ生成
      # 生成プロセスをひとつだけにするために、プロセスロックする
      File.open(cache_lock_path, 'w') do |f|
        if f.flock(File::LOCK_EX | File::LOCK_NB) then	
          begin
            require 'db'
            require 'utils'
            require 'time'
            require 'erubis'
            include Erubis::XmlHelper
            
            # DB接続
            db = DB.getInstance
            
            # ゲーム情報を取得
            require 'GameDao'
            require 'Game'
            game = GameDao.new.get_game_by_id(game_id)
            if game.nil? then
              res_status = "Status: 404 Not Found.\n"
              res_status = "Location: /404\n"
              raise "存在しないゲームIDが指定されました。(#{game_id})"
            end

            # リプレイ情報取得
            require 'Replay'
            res = db.exec(<<-"SQL")
              SELECT
                r.id,
                r.relative_file_path,
                EXTRACT(EPOCH FROM (t.play_timestamp - to_timestamp(0))) AS play_timestamp,
                t.player1_type1_id,
                t.player2_type1_id,
                gar1.rating AS player1_rating,
                gar1.ratings_deviation AS player1_ratings_deviation,
                gar1.matched_accounts AS player1_matched_accounts,
                gar2.rating AS player2_rating,
                gar2.ratings_deviation AS player2_ratings_deviation,
                gar2.matched_accounts AS player1_matched_accounts
              FROM
                replays r
                 LEFT OUTER JOIN
                   game_account_ratings gar1
                 ON
                   r.game_id = gar1.game_id
                   AND r.player1_account_id = gar1.account_id
                   AND r.player1_type1_id = gar1.type1_id
                   AND gar1.ratings_deviation < 150
                , track_records t
                 LEFT OUTER JOIN
                   game_account_ratings gar2
                 ON
                   t.game_id = gar2.game_id
                   AND t.player2_account_id = gar2.account_id
                   AND t.player2_type1_id = gar2.type1_id
                   AND gar2.ratings_deviation < 150
              WHERE
                r.game_id = #{game_id.to_i}
                AND r.track_record_id = t.id
              ORDER BY
                r.id DESC
              LIMIT
                1000
            SQL
            
            res.each do |r|
              replay = Replay.new
              res.num_fields.times do |i|
                replay.instance_variable_set("@#{res.fields[i]}", r[i])
              end
              replay.play_timestamp = Time.at(replay.play_timestamp.to_i)
              replays << replay
            end
            res.clear
            
            # 対戦時刻順でソート
            # replays = replays.sort_by { |r| -1 * r.play_timestamp.to_i }
            replays = replays.sort_by { |r| -1 * (r.player1_rating.to_i || -9999) }
            # replays = replays.sort_by do |r|
            # -1 * ([r.player1_rating, r.player2_rating].delete_if{|rating| rating.nil? || rating == "" }.map{|rating| rating.to_i}.max || -9999)
            #end
            
            # ゲーム情報取得
            require 'GameDao'
            games = GameDao.new.get_games(replays.map{|r| r.game_id}.uniq)
            
            # キャラ情報取得
            require 'GameType1Dao'
            game_type1s = GameType1Dao.new.get_by_game_ids([game_id.to_i])
            
            # twitter データ取得
            require 'ExServiceAccountDao'
            esa_dao = ExServiceAccountDao.new
            account_twitter_data = esa_dao.get_twitter_data_by_account_ids(replays.map{|r| r.player1_account_id}.uniq)
           
          rescue => ex
            res_status = "Status: 500 Server Error\n"
            res_body << "サーバーエラーです。ごめんなさい。\n" unless res_body
            raise ex
          ensure
            db.close  if db
          end

          ### キャッシュHTML出力
          
          # 内部リンク 部生成
          link_internal_html = Erubis::Eruby.new(File.read(LINK_INTERNAL_ERB_PATH)).result(binding)
          # リンク 部生成
          link_html = Erubis::Eruby.new(File.read(LINK_ERB_PATH)).result(binding)
          # footer 部生成
          footer_html = Erubis::Eruby.new(File.read(FOOTER_ERB_PATH)).result(binding)
          
          # キャッシュHTML/ヘッダ出力
          File.open(cache_html_path, 'w') do |w|
            w.flock(File::LOCK_EX)
            w.puts Erubis::Eruby.new(File.read("#{File::basename(__FILE__, '.*')}.erb")).result(binding)
            File.open(cache_html_header_path, 'w') do |wh|
              wh.flock(File::LOCK_EX)
              wh.puts "Content-Type:text/html; charset=utf-8"
              wh.puts "Last-Modified: #{now.httpdate}"
              wh.puts "Expires: #{cache_expires.httpdate}"
            end
          end

        else
          logger.info("Info: #{cache_lock_path} is locked. Wait unlocked.\n")
          # 先行プロセスがキャッシュを書き出すのを待つ
          f.flock(File::LOCK_EX)
          f.flock(File::LOCK_UN)
          is_cache_used = true
        end	# if f.flock(File::LOCK_EX | File::LOCK_NB) then	
      end # File.open(cache_lock_path, 'w') do |f|
    else
      is_cache_used = true
    end # unless (File.exist?(cache_html_path) and File.exist?(cache_xml_path)) then
    
    ### 結果をセット
    res_status = ""
    File.open(cache_html_path, 'r') do |f|
      f.flock(File::LOCK_SH)
      res_body = f.read()
      File.open(cache_html_header_path, 'r') do |fh|
        fh.flock(File::LOCK_SH)
        res_header = fh.read()
      end
    end
    
    # 304 Not Modified 判定
    if ENV['HTTP_IF_MODIFIED_SINCE'] then
      if res_header =~ /Last-Modified:\s*([^\n]+)/i then
        last_modified = Time.httpdate($1)
        # 古いブラウザによる RFC2616 違反の HTTP ヘッダに対応
        since = Time.httpdate(ENV['HTTP_IF_MODIFIED_SINCE'].sub(/;.*\z/, ""))
        if last_modified <= since then
          res_status = "Status: 304 Not Modified\n"
        end
      end
    end
      
  rescue => ex
    res_status = "Status: 500 Server Error\n" unless res_status
    res_body = "サーバーエラーです。ごめんなさい。\n" unless res_body
    File.open(ERROR_LOG_PATH, 'a') do |err_log|
      err_log.puts "#{now.to_s} #{File::basename(__FILE__)} #{REVISION}" 
      err_log.puts ENV['QUERY_STRING']
      err_log.puts ex.to_s
      err_log.puts ex.backtrace.join("\n").to_s
      err_log.puts
    end
  end
else
  res_status = "Status: 400 Bad Request\n"
  res_body = "400 Bad Request\n"
end

begin
# HTTP レスポンス送信
print res_status
print res_header
print "\n"
print res_body

# ログ記録
  times = Process.times
  logger.debug(
    [
      File::basename(__FILE__),
      REVISION,
      Time.now - now,
      times.utime + times.stime,
      times.utime,
      times.stime,
      times.cutime,
      times.cstime,
      is_cache_used.to_s,
      ENV['QUERY_STRING']
    ].join("\t")
  )
rescue
end

