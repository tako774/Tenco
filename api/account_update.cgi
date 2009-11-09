#!/usr/bin/ruby

begin
	# 開始時刻
	now = Time.now

	### アカウント情報更新 API ###
	REVISION = 'R0.01'

	$LOAD_PATH.unshift '../common'
	$LOAD_PATH.unshift '../entity'

	require 'rexml/document'
	require 'kconv'
	require 'yaml'
	require 'time'
	require 'logger'
	require 'utils'
	require 'setting'
	require 'cryption'

	# 設定読み込み
	CFG = Setting.new
	# TOP ページ URL
	TOP_URL = CFG['top_url']

	# ログファイルパス
	LOG_PATH = "../log/log_#{now.strftime('%Y%m%d')}.log"
	ACCESS_LOG_PATH = "../log/access_#{now.strftime('%Y%m%d')}.log"
	ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

	# バリデーション用定数
	ACCOUNT_NAME_REGEX = /\A[a-zA-Z0-9_]+\z/
	ACCOUNT_PASSWORD_BYTE_MIN = 4
	ACCOUNT_PASSWORD_BYTE_MAX = 16
	ACCOUNT_PASSWORD_REGEX = /\A[\x01-\x7F]+\z/
	ACCOUNT_MAIL_ADDRESS_BYTE_MAX = 256
	ACCOUNT_MAIL_ADDRESS_REGEX = /\A[\x01-\x7F]+@(([-a-z0-9]+\.)*[a-z]+|\[\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\])\z/

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
		query = {} # クエリストリング
		source = nil # POSTデータ
		db = nil   # DB接続 
		account = nil # アカウント情報
		MAX_POST_DATA_BYTES = 10000; # 最大受付ポストデータサイズ
		
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
		
		account_name = query['account_name']
		account_password = query['account_password']
		new_mail_address = query['new_mail_address']
		new_account_password = query['new_account_password']
		new_show_ratings_flag = query['new_show_ratings_flag']
		lock_version = query['lock_version']
		
		new_account_password = nil if new_account_password == ''
		new_show_ratings_flag = nil if new_show_ratings_flag == ''
		
		# バリデーション
		unless (
			!new_account_password or (
				new_account_password =~ ACCOUNT_PASSWORD_REGEX and
				new_account_password.length >= ACCOUNT_PASSWORD_BYTE_MIN and 
				new_account_password.length <= ACCOUNT_PASSWORD_BYTE_MAX and
				new_account_password != account_name # アカウント名とパスワードが一緒ならはじく
			)
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body << "・パスワードに利用可能な文字は、半角英数記号のみです\n"
			res_body << "・パスワードの長さは、#{ACCOUNT_PASSWORD_BYTE_MIN}バイト以上#{ACCOUNT_PASSWORD_BYTE_MAX}バイト以内に制限しています\n"
			res_body << "・パスワードとアカウント名は、別の文字列にしてください\n"
			raise "アカウントの新規登録に失敗しました。入力値バリデーションエラー"
		end
		
		unless (
			!new_mail_address or
			new_mail_address == '' or (
				new_mail_address =~ ACCOUNT_MAIL_ADDRESS_REGEX and
				new_mail_address.length <= ACCOUNT_MAIL_ADDRESS_BYTE_MAX
			)
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body << "・メールアドレスは正しい形式で入力してください\n"
			res_body << "・メールアドレスの長さは、#{ACCOUNT_MAIL_ADDRESS_BYTE_MAX}バイト以内に制限しています\n"
			raise "アカウントの新規登録に失敗しました。入力値バリデーションエラー"
		end
					
		unless (
			!new_show_ratings_flag or
			new_show_ratings_flag == '0' or
			new_show_ratings_flag == '1'
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body << "・レート表示設定の値が不正です\n"
			raise "アカウントの新規登録に失敗しました。入力値バリデーションエラー"
		end
		
		# DB接続
		require 'db'
		db = DB.getInstance
		
		# アカウント更新
		require 'authentication'
		begin
			account = Authentication.update(account_name, account_password, new_mail_address, new_account_password, new_show_ratings_flag, lock_version)
		rescue => ex
			res_status = "Status: 400 Bad Request\n"
			res_body = "アカウント更新に失敗しました。ページを読み込みなおして、再度実行してください。\n"
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
		root.add_element('lock_version').add_text(account.lock_version.to_s)
							
		### 結果をセット
		res_status = "Status: 200 OK\n"
		res_header = "content-type:text/xml; charset=utf-8\n"
		res_body = xml.to_s
		
	rescue => ex
		unless res_status then
			res_status = "Status: 500 Internal Server Error\n" 
			res_body << "アカウントの新規登録に失敗しました。サーバーエラーです。\n"
			res_body << "サーバーが不調かもしれません。。。時間をおいてやり直してください。\n"
		end
			File.open(ERROR_LOG_PATH, 'a') do |err_log|
				err_log.puts "#{DateTime.now.to_s} account.cgi" 
				err_log.puts source
				err_log.puts ex.to_s
				err_log.puts ex.backtrace.join("\n").to_s
				err_log.puts
			end
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
res_header = "content-type:text/plain; charset=utf-8\n" unless res_header
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
			source
		].join("\t")
	)
rescue
end

exit
