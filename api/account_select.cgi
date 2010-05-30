#!/usr/bin/ruby

begin
	# 開始時刻
	now = Time.now

	### アカウント情報取得 API ###
	REVISION = 'R0.02'
	DEBUG = false

	# TOP ディレクトリ
	TOP_DIR = '..'

	$LOAD_PATH.unshift "#{TOP_DIR}/common"
	$LOAD_PATH.unshift "#{TOP_DIR}/entity"

	require 'logger'
	require 'utils'
	require 'cryption'
	require 'setting'
		
	# 設定読み込み
	CFG = Setting.new
	# TOP ページ URL
	TOP_URL = CFG['top_url']
	# ログファイルパス
	LOG_PATH = "#{TOP_DIR}/log/log_#{now.strftime('%Y%m%d')}.log"
	ACCESS_LOG_PATH = "#{TOP_DIR}/log/access_#{now.strftime('%Y%m%d')}.log"
	ERROR_LOG_PATH = "#{TOP_DIR}/log/error_#{now.strftime('%Y%m%d')}.log"
	# キャッシュフォルダパス
	CACHE_DIR = "#{TOP_DIR}/cache/eternal/#{File::basename(__FILE__)}"
	# キャッシュロックフォルダパス
	CACHE_LOCK_DIR = "#{TOP_DIR}/cache/eternal/lock/#{File::basename(__FILE__)}"
	# キャッシュをつかったかどうか
	is_cache_used = false

	# HTTP/HTTPSレスポンス文字列
	res_status = nil
	res_header = ''
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
		query = {} # クエリストリング
		source = nil # POSTデータ
		db = nil   # DB接続 
		account = nil # アカウント情報
		
		# バリデーション用定数
		MAX_POST_DATA_BYTES = 10000; # 最大受付ポストデータサイズ
		ACCOUNT_NAME_REGEX = /\A[a-zA-Z0-9_]+\z/
		ACCOUNT_PASSWORD_REGEX = /\A[\x01-\x7F]+\z/
		
		# ポストデータ取得
		if ENV['CONTENT_LENGTH'].to_i > MAX_POST_DATA_BYTES then
			res_status = "Status: 400 Bad Request\n"
			res_body = "ポストデータサイズが大きすぎます\nPost data size is too large.\n"
			raise "ポストデータサイズが大きすぎます"
		end
		source = STDIN.read(ENV['CONTENT_LENGTH'].to_i)
		
		# 入力データ分解
		query = parse_query_str(source)
		
		# 入力バリデーション
		unless (
			query['account_name'] and
			query['account_name'] =~ ACCOUNT_NAME_REGEX and
			query['account_password'] and
			query['account_password'] =~ ACCOUNT_PASSWORD_REGEX
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "入力データが正しくありません\ninput data validation error.\n"
			raise "input data validation error."
		end
		
		# 値設定
		account_name = query['account_name']
		account_password = query['account_password']
		
		# DB 接続
		require 'db'
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

		### XML生成
		require 'rexml/document'
		
		# XML生成
		xml = REXML::Document.new
		xml << REXML::XMLDecl.new('1.0', 'UTF-8')
		
		# account 要素生成
		root = xml.add_element('account')
		root.add_element('name').add_text(account.name.to_s)
		root.add_element('mail_address').add_text(Cryption.decrypt(account.encrypted_mail_address.to_s))
		root.add_element('show_ratings_flag').add_text(account.show_ratings_flag.to_s)
		root.add_element('allow_edit_profile').add_text(account.allow_edit_profile.to_s)
		root.add_element('lock_version').add_text(account.lock_version.to_s)
							
		### 結果をセット
		res_status = "Status: 200 OK\n"
		res_header = "content-type:text/xml; charset=utf-8\n"
		res_body = xml.to_s
				
	rescue => ex
		res_status = "Status: 500 Server Error\n" unless res_status
		res_body << "サーバーエラーが発生しました。ごめんなさい。（#{now.strftime('%Y/%m/%d %H:%M:%S')}）\n"
		File.open(ERROR_LOG_PATH, 'a') do |err_log|
			err_log.puts "#{now.strftime('%Y/%m/%d %H:%M:%S')} #{File::basename(__FILE__)} Rev.#{REVISION}" 
			err_log.puts source
			err_log.puts ex.to_s
			err_log.puts ex.backtrace.join("\n").to_s
			err_log.puts
		end
	ensure
		# DB接続を閉じる
		db.close if db
	end
else
	res_status = "Status: 400 Bad Request\n"
	res_body = "400 Bad Request\n"
end

begin
# HTTP レスポンス送信
res_status "Status: 500 Internal Server Error\n" unless res_status
res_header = "content-type:text/plain; charset=utf-8\n" unless res_header
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
			source
		].join("\t")
	)
rescue
end
