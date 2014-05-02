#!/usr/bin/ruby

begin
  # 開始時刻
  now = Time.now

  ### リプレイアップロード API ###
  REVISION = 'R0.03'
  DEBUG = false

  $LOAD_PATH.unshift '../common'
  $LOAD_PATH.unshift '../entity'
  $LOAD_PATH.unshift '../dao'

  require 'rexml/document'
  require 'kconv'
  require 'yaml'
  require 'time'
  require 'logger'
  require 'fileutils'
  require 'cgi'
  
  require 'utils'
  require 'cryption'
  require 'db'

  require 'TrackRecordDao'
  require 'ReplayDao'
  require 'Replay'
  require 'GameDao'
  
  # ログファイルパス
  LOG_PATH = "../log/log_#{now.strftime('%Y%m%d')}.log"
  ACCESS_LOG_PATH = "../log/access_#{now.strftime('%Y%m%d')}.log"
  ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"
  
  # リプレイディレクトリパス
  REPLAY_DAT_DIR = "../replay"
  
  # 1ディレクトリあたりの最大ファイル数
  MAX_FILE_NUM_PER_DIR = 10 ** 5

  # 受け入れ最大受信バイト数
  MAX_CONTENT_LENGTH = 256 * 1024
  
  # バリデーション用定数
  ID_REGEX = /\A[0-9]+\z/
  ACCOUNT_NAME_REGEX = /\A[a-zA-Z0-9_]+\z/
  ACCOUNT_PASSWORD_REGEX = /\A[\x01-\x7F]+\z/
      
  # HTTP/HTTPSレスポンス文字列
  res_status = "Status: 500 Internal Server Error\n"
  res_header = ''
  res_body = ""

  # ログ開始
  log = Logger.new(LOG_PATH)
  log.level = Logger::DEBUG
  log_msg = "" # ログに出すメッセージ

  # アクセスログ記録
  access_logger = Logger.new(ACCESS_LOG_PATH)
  access_logger.level = Logger::DEBUG
  access_logger.info(
    [
      "",
      now.strftime('%Y/%m/%d %H:%M:%S'),
      ENV['REMOTE_ADDR'],
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

if ENV['REQUEST_METHOD'] == 'POST' then
  begin
    source_length = ENV['CONTENT_LENGTH'].to_i # 受信バイト数
    cgi = CGI.new
    meta_info = cgi.params['meta_info'][0].read
    replay_content = cgi.params['replay_file'][0].read
    game = nil # ゲーム情報
    type1s = {} # type1_id => type1_name
        
    # コンテント長のバリデーション
    if source_length > MAX_CONTENT_LENGTH then
      res_status = "Status: 400 Bad Request\n"
      res_body = "送信されたデータサイズが大きすぎます。\n"
      raise "送信されたデータサイズが大きすぎます（#{source_length} > #{MAX_CONTENT_LENGTH}）。"
    end
    
    # 受信データ文字コードチェック
    unless (Kconv.isutf8(meta_info)) then
      res_status = "Status: 400 Bad Request\n"
      res_body = "エラー：入力された文字コードがUTF8ではないようです"
      raise "input char code validation error."
    end
    
    # 受信XMLデータをパース
    xml_data = REXML::Document.new(meta_info)
    data = xml_data.elements['/replayPosting']
    game_data = data.elements['game'] # 複数の game_id を含むデータには未対応なので、一番最初の game タグのみ処理。残りは無視。
    game_id = game_data.elements['id'].text.to_i
    account_name = data.elements['account/name'].text
    account_password = data.elements['account/password'].text
    trackrecord = {}
    game_data.elements['trackrecord'].each_child do |c|
      trackrecord[c.name] = c.text
    end
    
    # ヘッダバリデーション
    unless (
      account_name =~ ACCOUNT_NAME_REGEX and
      account_password =~ ACCOUNT_PASSWORD_REGEX and
      game_id.to_s =~ ID_REGEX
    ) then
      res_status = "Status: 400 Bad Request\n"
      res_body = "入力データが正しくありません\ninput data validation error.\n"
      raise "input data validation error."
    end
    
    # DB 接続
    db = DB.getInstance
    
    # アカウント認証
    # 認証失敗時は例外が投げられる
    require 'authentication'
    begin
      account = Authentication.login(account_name, account_password)
    rescue => ex
      res_status = "Status: 401 Unauthorized\n"
      res_body = "アカウント認証エラーです。\n"
      raise ex
    end
    
    # ゲームID存在確認
    game_dao = GameDao.new
    game = game_dao.get_games(game_id.to_s)
    if game.length == 0 then
      res_status = "Status: 400 Bad Request\n"
      res_body = "登録されていないゲームIDのデータが送信されています。\n"
      raise "受信ゲームIDがDBに存在しません（#{game_id.to_s}）"
    end
    
    # トランザクション開始
    db.exec("BEGIN TRANSACTION;")
    
    # リプレイファイルデータをDBに登録する
    begin
      
      # 対戦結果を取得
      play_timestamp = Time.iso8601(trackrecord['timestamp'].to_s).localtime.strftime("%Y-%m-%d %H-%M-%S")
      trackrecord = TrackRecordDao.new.get_id_by_timestamp(game_id, play_timestamp, account.name)
      
      log_msg = "#{data.elements['account/name'].text} #{play_timestamp} #{trackrecord.id if !trackrecord.nil?}"
      log_msg << "\t#{Time.now - now}"
      
      # 対戦結果が見つからない場合はエラー
      if trackrecord.nil? then
        raise "報告されたリプレイ対戦結果が見つかりません。\r\n"
      end
      
      ## リプレイファイルデータのDB登録
 
       # リプレイファイルDB登録
      replay = Replay.new
      replay.game_id = trackrecord.game_id
      replay.track_record_id = trackrecord.id
      replay.player1_account_id = trackrecord.player1_account_id
      replay.player1_type1_id = trackrecord.player1_type1_id
      replay = ReplayDao.new.insert(replay)
      
      # リプレイファイル保存パスの取得
      replay_path = "#{REPLAY_DAT_DIR}/#{replay.relative_file_path}"
      replay_dir_path = File.dirname(replay_path)
      
      # リプレイファイル保存
      FileUtils.mkdir_p(replay_dir_path) unless File.directory?(replay_dir_path) 
      File.open(replay_path, "wb") do |io|
        io.write replay_content
      end
      

      
    rescue => ex
      res_status = "Status: 400 Bad Request\n"
      res_body << "リプレイファイルの登録に失敗しました。\n"
      res_body << "すでに登録済みのデータが報告されているかもしれません。\n"
      res_body << "\n"
      raise ex
    else
      res_body << "リプレイファイルの登録に成功しました。\n"
    end
    
    # トランザクション終了
    db.exec("COMMIT;")
    res_body << "transaction finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

  rescue => ex
    res_status = "Status: 400 Bad Request\n" unless res_status
    res_body << "リプレイファイルの登録時にエラーが発生しました。ごめんなさい。（#{now.strftime('%Y/%m/%d %H:%M:%S')}）\n"
    File.open(ERROR_LOG_PATH, 'a') do |err_log|
      err_log.puts "#{now.strftime('%Y/%m/%d %H:%M:%S')} #{File::basename(__FILE__)} Rev.#{REVISION}" 
      err_log.puts meta_info
      err_log.puts ex.to_s
      err_log.puts ex.backtrace.join("\n").to_s
      err_log.puts
    end
  else
    res_status = "Status: 200 OK\n"
    res_body << "正常にリプレイファイル登録を実行しました。\n"
  ensure
    # DB接続を閉じる
    db.close if db
  end
else
  res_status = "Status: 400 Bad Request\n"
  res_body = "400 Bad Request\n"
end

# HTTP レスポンス送信
res_header = "content-type:text/plain; charset=utf-8\n"
print res_status
print res_header
print "\n"
print res_body

# ログ記録
begin
  times = Process.times
  log.debug(
    [
      File::basename(__FILE__),
      REVISION,
      Time.now - now,
      times.utime + times.stime,
      times.utime,
      times.stime,
      times.cutime,
      times.cstime,
      ENV['QUERY_STRING'].gsub(/\r\n|\n/, '\n')[0..99],
      log_msg
    ].join("\t")
  )
rescue
end

exit
