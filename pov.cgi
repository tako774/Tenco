#!/usr/bin/ruby

# POVページ作成CGI
begin
  # 開始時刻
  now = Time.now
  # リビジョン
  REVISION = 'R0.16'
  DEBUG = false

  $LOAD_PATH.unshift './common'
  $LOAD_PATH.unshift './entity'
  $LOAD_PATH.unshift './dao'

  require 'time'
  require 'logger'
  require 'utils'
  require 'setting'
  
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
    require 'segment_const'
    query = {} # クエリストリング
    
    # クエリストリング分解・取得
    query = parse_query_str(ENV['QUERY_STRING'])
    
    if (
      query['game_id'] and
      query['game_id'] !='' and
      query['pov_id'] and
      query['pov_id'] != ''
    ) then
      
      pov_id = query['pov_id'].to_i       # POV番号
      game_id = query['game_id'].to_i     # ゲーム番号
      output = query['output'] || 'html'  # 出力形式
      
      MAX_SHOW_NUM = 500 # 最大表示人数
      
      header_erb_path = "./#{File::basename(__FILE__, '.*')}_header.erb" # ヘッダーERBパス
      main_erb_path   = "./#{File::basename(__FILE__, '.*')}_#{pov_id}_main.erb" # メインERBパス
      link_internal_erb_path = "./link_internal.erb" # 関連POVリンクERBパス
      link_erb_path   = "./link.erb"       # リンクERBパス
      footer_erb_path = "./footer.erb"     # フッターERBパス
    
      # キャッシュフォルダがなければ生成
      Dir.mkdir(CACHE_BASE, 0700) unless File.exist?(CACHE_BASE)
      Dir.mkdir(CACHE_DIR, 0700) unless File.exist?(CACHE_DIR)
      Dir.mkdir(CACHE_LOCK_DIR, 0700) unless File.exist?(CACHE_LOCK_DIR)

      # キャッシュパス設定・プロセスロックファイルパス設定
      cache_html_path = "#{CACHE_DIR}/#{File::basename(__FILE__)}_#{game_id}_#{pov_id}.html"
      cache_html_header_path  = "#{cache_html_path}.h"
      cache_lock_path = "#{CACHE_LOCK_DIR}/#{File::basename(__FILE__)}_#{game_id}_#{pov_id}.lock"
      
      # キャッシュパスのバリデーション
      if cache_html_path =~ /\.{2}/ or cache_lock_path =~ /\.{2}/ then
        raise "ディレクトリトラバーサルの疑いがあります"
      end
    
      # デバッグ時か、キャッシュが無いかあってもファイルサイズが０か、
      # ロックファイルが無ければ（＝キャッシュの再生成を行う条件）、キャッシュ生成
      unless (
        !DEBUG and 
        File.exist?(cache_html_path) and File.size(cache_html_path) != 0 and
        File.exist?(cache_html_header_path) and File.size(cache_html_header_path) != 0 and
        File.exist?(cache_lock_path)
      ) then
            
        ### キャッシュ生成
        # 生成プロセスをひとつだけにするために、プロセスロックする
        File.open(cache_lock_path, 'w') do |f|
          if f.flock(File::LOCK_EX | File::LOCK_NB) then
          
            game = nil             # ゲーム情報
            pov_classes = []  # ゲームＰＯＶクラス情報
            prizes = []            # 達成情報
            type1 = {}             # 対象の Type1 区分値
            ratings = {}
            ratings_each_type1 = {}
            account_ids = [] # アカウントID
            account_twitter_data = [] # アカウントのツイッター情報
          
            ### データ取得
            begin
              require 'utils'
              require 'erubis'
              include Erubis::XmlHelper
              require 'html_helper'
              
              # DB接続
              require 'db'
              db = DB.getInstance
              
              ## ゲーム情報を取得
              require 'Game'
              res = db.exec(<<-"SQL")
                SELECT
                  *
                FROM
                  games
                WHERE
                  id = #{game_id.to_i}
              SQL
              
              if res.num_tuples != 1 then
                res.clear
                res_status = "Status: 400 Bad Request\n"
                res_body = "ゲーム情報が登録されていません\n"
                raise "ゲーム情報が登録されていません"
              else
                game = Game.new
                res.fields.length.times do |i|
                  game.instance_variable_set("@#{res.fields[i]}", res[0][i])
                end
                res.clear
              end
              
              ## POV情報取得
              require 'Pov'
              res = db.exec(<<-"SQL")
                SELECT
                  *
                FROM
                  povs
                WHERE
                  id  = #{pov_id.to_i}
              SQL
              
              if res.num_tuples != 1 then
                res.clear
                res_status = "Status: 400 Bad Request\n"
                res_body = "ゲームPOV情報が登録されていません\n"
                raise "ゲームPOV情報が登録されていません"
              else
                pov = Pov.new
                res.fields.length.times do |i|
                  pov.instance_variable_set("@#{res.fields[i]}", res[0][i])
                end
                res.clear
              end
              
              ## POVのクラス区分取得
              require 'PovClass'
              res = db.exec(<<-"SQL")
                SELECT
                  *
                FROM
                  pov_classes
                WHERE
                  pov_id = #{pov_id.to_i}
                ORDER BY
                  show_order
              SQL
              
              if res.num_tuples < 1 then
                res.clear
                res_status = "Status: 500 Server Error\n"
                res_body = "サーバーエラーです。ごめんなさい。\n"
                res_body << "（該当ゲームPOVに対応するクラス区分が登録されていません）\n"
                raise "ゲームPOVに対応するクラス区分が登録されていません"
              else
                res.each do |r|
                  pov_class = PovClass.new
                  res.fields.length.times do |i|
                    pov_class.instance_variable_set("@#{res.fields[i]}", r[i])
                  end
                  pov_classes << pov_class
                end
              end
              res.clear
              
              
              ## 該当ゲームＰＯＶを観点とする達成リストを取得
              require 'Prize'
              res = db.exec(<<-"SQL")
                SELECT
                  *
                FROM
                  prizes
                WHERE
                      game_id = #{game_id.to_i}
                  AND pov_id = #{pov_id.to_i}
                ORDER BY
                  type1_id
              SQL
              
              if res.num_tuples < 1 then
                # ToDo:ゲームＰＯＶを観点とする達成リストがないときの処理
              else
                res.each do |r|
                  prize = Prize.new
                  res.fields.length.times do |i|
                    prize.instance_variable_set("@#{res.fields[i]}", r[i])
                  end
                  prizes << prize
                end
              end
              res.clear
              
              ## 達成したアカウントのレート情報取得
              require 'GameAccountRating'
              res = db.exec(<<-"SQL")
                SELECT
                  r.*,
                  ga.rep_name,
                  pa.pov_class_value,
                  a.name AS account_name,
                  a.show_ratings_flag AS show_ratings_flag,
                  ga.cluster_id,
                  gc.name2 AS cluster_name
                FROM
                  accounts a,
                  game_accounts ga
                    LEFT OUTER JOIN
                    game_clusters gc
                  ON
                    ga.game_id = gc.game_id
                    AND ga.cluster_id = gc.cluster_id,
                  game_account_ratings r,
                  prize_accounts pa,
                  prizes p,
                  pov_classes pc
                WHERE
                      p.game_id = #{game_id.to_i}
                  AND p.pov_id = #{pov_id.to_i}
                  AND pa.prize_id = p.id
                  AND r.game_id = #{game_id.to_i}
                  AND r.account_id = pa.account_id
                  AND r.type1_id = pa.type1_id
                  AND pc.pov_id = #{pov_id.to_i}
                  AND pc.value = pa.pov_class_value
                  AND ga.account_id = r.account_id
                  AND ga.game_id = #{game_id.to_i}
                  AND a.id = r.account_id
                  AND a.del_flag = 0
                ORDER BY
                  pc.show_order,
                  #{"r.matched_accounts DESC," if pov_id.to_i == 3}
                  r.game_type1_ratings_rank,
                  r.rating DESC,
                  r.ratings_deviation
                  #{"LIMIT #{MAX_SHOW_NUM}" if pov_id.to_i != 2}
                SQL
              
              account_ids_hash = {}
              res.each do |r|
                rating = GameAccountRating.new
                res.fields.length.times do |i|
                  rating.instance_variable_set("@#{res.fields[i]}", r[i])
                end
                rating.cluster_name ||= rating.cluster_id ? "第#{rating.cluster_id}" : "（新参加）"
                ratings[rating.pov_class_value.to_i] ||= []
                ratings[rating.pov_class_value.to_i] << rating
                ratings_each_type1[rating.type1_id.to_i] ||= {}
                ratings_each_type1[rating.type1_id.to_i][rating.pov_class_value.to_i] ||= []
                ratings_each_type1[rating.type1_id.to_i][rating.pov_class_value.to_i] << rating
                account_ids_hash[rating.account_id.to_i] = nil
              end
              res.clear
              
              # Twitter データ取得
              require 'ExServiceAccountDao'
              esa_dao = ExServiceAccountDao.new
              account_twitter_data = esa_dao.get_twitter_data_by_account_ids(account_ids_hash.keys)
              
              # Type1 区分値取得
              res = db.exec(<<-"SQL")
                SELECT
                  type1_id,
                  name
                FROM
                  game_type1s
                WHERE
                  game_id = #{game_id.to_i}
              SQL
              
              res.each do |r|
                type1[r[0].to_i] = r[1]
              end
              res.clear
              
              # 仮想 Type1 区分値取得
              SEG_V[:virtual_type1].each_value do |seg|
                type1[seg[:value].to_i] = seg[:name]
              end
              
            rescue => ex
              res_status = "Status: 500 Server Error\n"
              res_body << "サーバーエラーです。ごめんなさい。\n" unless res_body
              raise ex
            ensure
              db.close  if db
            end
            
            ### キャッシュHTML出力
            
            # header 部生成
            header_html = Erubis::Eruby.new(File.read(header_erb_path)).result(binding)
            # main 部生成
            main_html = Erubis::Eruby.new(File.read(main_erb_path)).result(binding)
            # 内部リンク 部生成
            link_internal_html = Erubis::Eruby.new(File.read(link_internal_erb_path)).result(binding)
            # リンク 部生成
            link_html = Erubis::Eruby.new(File.read(link_erb_path)).result(binding)
            # footer 部生成
            footer_html = Erubis::Eruby.new(File.read(footer_erb_path)).result(binding)
          
            File.open(cache_html_path, 'w') do |w|
              w.flock(File::LOCK_EX)
              if DEBUG then
                erb_src = Erubis::Eruby.new(File.read("#{File::basename(__FILE__, '.*')}.erb")).src
                File.open("#{File::basename(__FILE__, '.*')}.erb.rb", 'w') do |s|
                  s.puts erb_src
                end
              end
              w.puts Erubis::Eruby.new(File.read("#{File::basename(__FILE__, '.*')}.erb")).result(binding)
              # ヘッダ出力
              File.open(cache_html_header_path, 'w') do |wh|
                wh.flock(File::LOCK_EX)
                wh.puts "Content-Type:text/html; charset=utf-8"
                wh.puts "Last-Modified: #{now.httpdate}"
                wh.puts "Expires: #{cache_expires.httpdate}"
              end

            end	
          else
            logger.info("Info: #{cache_lock_path} is locked.\n")
            # 先行プロセスがキャッシュを書き出すのを待つ
            f.flock(File::LOCK_EX)
            f.flock(File::LOCK_UN)
            is_cache_used = true
          end	# if f.flock(File::LOCK_EX | File::LOCK_NB) then
        end # File.open(cache_lock_path, 'w') do |f|
      
      else
        is_cache_used = true
      end # unless (File.exist?(cache_html_path) then
    
    
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
    
    else
      res_status = "Status: 400 Bad Request\n"
      res_body = "400 Bad Request\n"
    end # if (query['game_id'] and query['game_id'] !='' and query['pov_id'] and query['pov_id'] != '') then
    
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
      ENV['QUERY_STRING'].gsub(/\r\n|\n/, '\n')[0..99]
    ].join("\t")
  )
rescue
end

