#!/usr/bin/ruby

begin
	# 開始時刻
	now = Time.now

	### アカウントプロフィール取得 API ###
	REVISION = 'R0.01'
	DEBUG = false

	$LOAD_PATH.unshift "#{File.expand_path(File.dirname(__FILE__))}/../common"
	$LOAD_PATH.unshift "#{File.expand_path(File.dirname(__FILE__))}/../entity"
	$LOAD_PATH.unshift "#{File.expand_path(File.dirname(__FILE__))}/../dao"

	require 'rexml/document'
	require 'kconv'
	require 'yaml'
	require 'time'
	require 'logger'
	require 'erubis'
	include Erubis::XmlHelper
	
	require 'utils'
	require 'setting'
	
	require 'authentication'
	
	require 'AccountProfileDao'
	require 'ProfilePropertyDao'
	
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


if ENV['REQUEST_METHOD'] == 'POST' then
	begin
		### 変数
		db = nil   # DB接続 
		
		query = {} # クエリストリング
		source = nil # POSTデータ
		
		account_name = nil # アカウント名
		account_password = nil # アカウントパスワード
		account = nil # アカウント情報
		account_profiles = [] # アカウントプロフィール情報
		profile_properties = [] # プロフィールプロパティ情報
		profile_classes = {} # クラス別プロフィールプロパティ情報
		
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

		# 入力バリデーション
		unless (
			account_name and
			account_name =~ ACCOUNT_NAME_REGEX
			account_password and
			account_password =~ ACCOUNT_PASSWORD_REGEX
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "エラー：入力アカウントデータが正しくありません\ninput data validation error.\n"
			raise "input account data validation error."
		end
		
		# DB 接続
		require 'db'
		db = DB.getInstance
		
		# アカウント認証
		# 認証失敗時は例外が投げられる
		begin
			account = Authentication.login(account_name, account_password)
		rescue => ex
			res_status = "Status: 401 Unauthorized\n"
			res_body = "アカウント認証エラーです。\n"
			raise ex
		end
		
		# アカウントプロフィール情報を取得
		account_profiles = AccountProfileDao.new.get_by_account_id(account.id)
		
		# プロフィールプロパティ一覧を取得
		profile_properties = ProfilePropertyDao.new.get_all()
		profile_properties.each do |pp|
			profile_classes[pp.class_name] ||= {}
			profile_classes[pp.class_name][:display_name] = pp.class_display_name
			profile_classes[pp.class_name][:property] ||= []
			profile_classes[pp.class_name][:property] << pp
		end
		
		# 登録済みの場合は登録済みフラグを立てる
		profile_properties.each do |pp|
			if (
			  account_profiles.find { |ap| ap.profile_property_id == pp.id } 
			) then
				pp.is_registered = 1
			else
				pp.is_registered = 0
			end
		end
		
	rescue => ex
		unless res_status then
			res_status ||= "Status: 500 Internal Server Error\n" 
			res_body << "プロフィール情報の取得に失敗しました。サーバーエラーです。\n"
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

		### XML生成
		require 'rexml/document'
		
		# XML生成
		xml = REXML::Document.new
		xml << REXML::XMLDecl.new('1.0', 'UTF-8')
		
		# account 要素生成
		root = xml.add_element('account_profiles')
		
		account_e = root.add_element('account')
		account_e.add_element('name').add_text(h(account.name))
		
		# profile 要素生成
		account_profiles.each do |ap|
			profile_e = account_e.add_element('profile')
			profile_e.add_element('id').add_text(ap.id.to_i.to_s)
			# CData.new は引数に ']]>' があるとエラーになるが、htmlエスケープしているので発生しない
			profile_e.add_element('name').add_text(h(ap.name))
			profile_e.add_element('display_name').add_text(h(ap.display_name))
			profile_e.add_element('value').add(REXML::CData.new(h(ap.value)))
			profile_e.add_element('uri').add(REXML::CData.new(h(ap.uri)))
			profile_e.add_element('visibility').add_text(ap.is_visible.to_i.to_s)
		end
		
		# property 要素生成
		profile_classes.each do |class_name, pc|
			profile_class_e = root.add_element('profile_classes')
			profile_class_e.add_element('class_name').add_text(h(class_name))
			profile_class_e.add_element('class_display_name').add_text(h(pc[:display_name]))
			pc[:property].each do |pp|
				property_e = profile_class_e.add_element('property')
				property_e.add_element('name').add_text(h(pp.name))
				property_e.add_element('display_name').add_text(h(pp.display_name))
				property_e.add_element('is_unique').add_text(pp.is_unique.to_i.to_s)
				property_e.add_element('is_registered').add_text(pp.is_registered.to_i.to_s)
			end
		end
		
		### 結果をセット
		res_status = "Status: 200 OK\n"
		res_header = "content-type:text/xml; charset=utf-8\n"
		res_body = xml.to_s
				
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
