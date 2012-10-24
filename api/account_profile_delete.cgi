#!/usr/bin/ruby

begin
	# 開始時刻
	now = Time.now

	### アカウントプロフィール削除 API ###
	REVISION = 'R0.02'
	DEBUG = false

	$LOAD_PATH.unshift "#{File.expand_path(File.dirname(__FILE__))}/../common"
	$LOAD_PATH.unshift "#{File.expand_path(File.dirname(__FILE__))}/../entity"
	$LOAD_PATH.unshift "#{File.expand_path(File.dirname(__FILE__))}/../dao"

	require 'rexml/document'
	require 'kconv'
	require 'yaml'
	require 'time'
	require 'logger'
	
	require 'utils'
	require 'setting'
	
	require 'authentication'
  
	require 'AccountDao'
	require 'AccountProfileDao'
	require 'ProfilePropertyDao'
	require 'ExServiceDao'
  require 'AccountExServiceAccountDao'
	
	# 設定読み込み
	CFG = Setting.new
	# TOP ページ URL
	TOP_URL = CFG['top_url']

	# ログファイルパス
	LOG_PATH = "../log/log_#{now.strftime('%Y%m%d')}.log"
	ACCESS_LOG_PATH = "../log/access_#{now.strftime('%Y%m%d')}.log"
	ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

	# バリデーション用定数
	MAX_POST_DATA_BYTES = 1000; # 最大受付ポストデータサイズ
	ACCOUNT_NAME_REGEX = /\A[a-zA-Z0-9_]+\z/
	ACCOUNT_PASSWORD_REGEX = /\A[\x01-\x7F]+\z/

	# HTTP/HTTPSレスポンス文字列
	res_status = nil
	res_header = ''
	res_body = ''

	# ログ開始
	log = Logger.new(LOG_PATH)
	log.level = Logger::DEBUG

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
		### 変数
		db = nil   # DB接続 
		
		query = {} # クエリストリング
		source = nil # POSTデータ
		
		account_name = nil # アカウント名
		account_password = nil # アカウントパスワード
		account = nil # アカウント情報
		account_profile_id = nil # アカウントプロフィールID
    
    EX_SERVICE_NAME_TWITTER = "twitter"
		TWITTER_PROPERTY_NAME = "twitter"
		
		# ポストデータ取得
		if ENV['CONTENT_LENGTH'].to_i > MAX_POST_DATA_BYTES then
			res_status = "Status: 400 Bad Request\n"
			res_body = "ポストデータサイズが大きすぎます\nPost data size is too large.\n"
			raise "ポストデータサイズが大きすぎます"
		end
		source = STDIN.read(ENV['CONTENT_LENGTH'].to_i)
		
		# 入力データ分解
		query = parse_query_str(source)
		
		# 値設定
		account_name = query['account_name']
		account_password = query['account_password']
		account_profile_id = query['account_profile_id'].to_i
		
		# 入力バリデーション
		unless (
			account_name and
			account_name =~ ACCOUNT_NAME_REGEX
			account_password and
			account_password =~ ACCOUNT_PASSWORD_REGEX
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "エラー：入力アカウントデータが正しくありません\ninput account data validation error.\n"
			raise "input account data validation error."
		end
		
		unless (
			account_profile_id and
			account_profile_id != 0
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "エラー：入力プロフィールデータが正しくありません\ninput  account_profile_id validation error.\n"
			raise "input account_profile_id validation error.(#{account_profile_id})"
		end
		
		# DB 接続
		require 'db'
		db = DB.getInstance
		
		# トランザクション開始
		db.exec("BEGIN TRANSACTION;")
							
		# アカウント認証
		# 認証失敗時は例外が投げられる
		begin
			account = Authentication.login(account_name, account_password)
		rescue => ex
			res_status = "Status: 401 Unauthorized\n"
			res_body = "アカウント認証エラーです。\n"
			raise ex
		end
		
		# アカウントプロフィール情報を削除
		account_profile = AccountProfileDao.new.delete_by_id(account_profile_id)
    
	  # twitter のプロフィール削除時には、アカウントのもつ外部サービスアカウント情報を削除
    pp_dao = ProfilePropertyDao.new
    profile_property = pp_dao.get_by_id(account_profile.profile_property_id)
    
    if profile_property.name == TWITTER_PROPERTY_NAME and
       screen_name = twitter_screen_name_from_uri(account_profile.uri) then
       
      ex_service_twitter = ExServiceDao.new.get_by_name(EX_SERVICE_NAME_TWITTER)
      AccountExServiceAccountDao.new.delete_by_ex_service_id_account_key(account.id, ex_service_twitter.id, screen_name)
    end
    
		# トランザクション終了
		db.exec("COMMIT;")
		res_body << "transaction finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

	rescue => ex
		unless res_status then
			res_status ||= "Status: 500 Internal Server Error\n" 
			res_body << "プロフィール情報の登録に失敗しました。サーバーエラーです。\n"
			res_body << "サーバーが不調かもしれません。。。時間をおいてやり直してください。\n"
		end
			File.open(ERROR_LOG_PATH, 'a') do |err_log|
				err_log.puts "#{DateTime.now.to_s} #{File::basename(__FILE__)}"
				err_log.puts source
				err_log.puts ex.to_s
				err_log.puts ex.backtrace.join("\n").to_s
				err_log.puts
			end
	else
		
		### 結果をセット
		res_status = "Status: 200 OK\n"
		res_header = "content-type:text/plain; charset=utf-8\n"
		res_body = "プロフィール情報を削除しました"
	ensure
		# DB切断
		db.close if db
	end
else
	res_status = "Status: 400 Bad Request\n"
	res_body = "400 Bad Request\n"
end

# HTTP レスポンス送信
res_status = "Status: 500 Internal Server Error\n" unless res_status
res_header << "content-type:text/plain; charset=utf-8\n" unless res_header
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
			ENV['QUERY_STRING'].gsub(/\r\n|\n/, '\n')[0..99]
		].join("\t")
	)
rescue
end

exit
