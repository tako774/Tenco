#!/usr/bin/ruby

begin
	# 開始時刻
	now = Time.now

	### アカウントプロフィール登録 API ###
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
	
  require 'ExService'
  require 'ExServiceAccount'
  require 'AccountExServiceAccount'
  
	require 'AccountDao'
	require 'AccountProfileDao'
	require 'ProfilePropertyDao'
	require 'ExServiceDao'
  require 'ExServiceAccountDao'
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
	VALUE_MAX_LENGTH = 16
	ACCOUNT_PROFILE_COUNT_MAX = 100
	MAX_URI_BYTES = 255
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
		profile_property = nil # プロフィールプロパティ情報
		account_profile_id = nil # 登録したアカウントプロフィールID
    
    EX_SERVICE_NAME_TWITTER = "twitter"
		TWITTER_PROPERTY_NAME = "twitter"
		STRIP_CHAR = "　\s\t\r\n\f\v"
		
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
		property_name = query['property_name']
		property_value = query['property_value'].sub!(/\A[#{STRIP_CHAR}]*(.*?)(?:[#{STRIP_CHAR}])*\z/uo, '\1')
		property_visibility = query['property_visibility'] || 1
		property_uri = query['property_uri'].strip
		
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
			property_name and
			property_name != "" and
			property_value and
			property_value != ""
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "エラー：入力プロフィールデータが正しくありません\ninput profile data validation error.\n"
			raise "input profile data validation error.(#{property_name}, #{property_value})"
		end

		unless (
			Kconv.isutf8(property_name) and
			Kconv.isutf8(property_value)
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "エラー：入力されたデータがUTF8ではないようです"
			raise "input tag_name char code validation error.(#{property_name}, #{property_value})"
		end

		if (property_value =~ /[\t\n\r\f\v]/) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "プロフィールの値にはタブ・改行・改ページを含めることは出来ません"
			raise "input profile value validation error."
		end
		
		profile_value_length = property_value.split(//u).length
		unless (
			profile_value_length <= VALUE_MAX_LENGTH
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "登録できるプロフィールの入力値の長さは#{VALUE_MAX_LENGTH}文字以下です"
			raise "input profile value length validation error (#{property_value})."
		end
		
		unless (
			property_visibility == "0" || property_visibility == "1"
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "表示非表示設定の値が不正です"
			raise "input profile visibility length validation error (#{property_visibility})."
		end
		
		if property_uri == "" then
			property_uri = nil
		elsif !property_uri.nil?
			unless validate_uri(property_uri) then
				res_status = "Status: 400 Bad Request\n"
				res_body = "URLの形式が不正です"
				raise "input profile uri value validation error (#{property_uri})."
			end
			
			unless property_uri.bytesize <= MAX_URI_BYTES
				res_status = "Status: 400 Bad Request\n"
				res_body = "URLは#{MAX_URI_BYTES}バイト以下でなければなりません"
				raise "input profile uri byte size validation error (#{property_uri})."
			end
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
		
		# Profile の保有数をチェック
		res = db.exec(<<-"SQL")
		  SELECT
		    count(*)
		  FROM
		    account_profiles
		  WHERE
			account_id = #{account.id.to_i}
		SQL
		
		if res[0][0].to_i >= ACCOUNT_PROFILE_COUNT_MAX then
			res.clear
			res_status = "Status: 400 Bad Request\n"
			res_body = "１アカウントあたり登録可能なプロフィール数（#{ACCOUNT_PROFILE_COUNT_MAX}）を超えています\n"
			raise "too many profiles for an account error."
		end
		
		res.clear

		# プロフィールプロパティ情報を取得
		profile_property = ProfilePropertyDao.new.get_by_name(property_name)
		if profile_property.nil? then
			res_status = "Status: 400 Bad Request\n" 
			res_body << "プロフィール情報の登録に失敗しました。\n"
			res_body << "該当するプロフィールのプロパティ名は存在しません(#{property_name})。\n"
			raise ex
		end
		
		# アカウントプロパティ情報を取得
		apd = AccountProfileDao.new
		account_profiles = apd.get_account_profiles_by_property_id(account.id, profile_property.id)
		
		# プロパティ情報がアカウントごとにひとつだけ登録可能なもので、すでに登録済みならエラー
		if (
		  profile_property.is_unique.to_i == 1 and
		  account_profiles.length > 0
		) then
			res_status = "Status: 409 Conflict\n" 
			res_body << "プロフィール情報の登録に失敗しました。\n"
			res_body << "入力されたプロフィールは、1アカウントに1つだけ登録可能です(#{profile_property.display_name})。\n"
			res_body << "表示がおかしい場合は、ページを再読込してください。\n"
			raise ex
		end
		
		# 登録しようとしたプロパティに、全く同一の値が登録済みの場合エラー
		if account_profiles.find { |ap| ap.value == property_value } then
			res_status = "Status: 409 Conflict\n" 
			res_body << "プロフィール情報の登録に失敗しました。\n"
			res_body << "入力されたプロフィールは登録済みです(#{profile_property.display_name}:#{property_value})。\n"
			raise ex
		end
		
		# プロフィール情報を登録
		account_profile_id = apd.add(account.id, profile_property.id, property_value, property_visibility, property_uri)
		
    # twitter のプロフィール登録時には、外部サービスアカウント情報を保存
    if property_name == TWITTER_PROPERTY_NAME and
       screen_name = twitter_screen_name_from_uri(property_uri) then
      
      ex_service_twitter = ExServiceDao.new.get_by_name(EX_SERVICE_NAME_TWITTER)
      ex_service_account = nil
      esa_dao = ExServiceAccountDao.new
      account_ex_service_account = AccountExServiceAccount.new
      aesa_dao = AccountExServiceAccountDao.new
      
      # 外部サービスアカウント情報のデータを取得、まだなければ登録
      unless ex_service_account = esa_dao.get_by_ex_service_name_account_key(ex_service_twitter.name, screen_name) then
        ex_service_account = ExServiceAccount.new
        ex_service_account.ex_service_id = ex_service_twitter.id
        ex_service_account.account_key = screen_name
        ex_service_account.request_update_flag = 1
        ex_service_account = esa_dao.insert(ex_service_account)
      end
      
      # Tenco!アカウントのもつ外部サービスアカウント情報を登録
      account_ex_service_account.account_id = account.id
      account_ex_service_account.ex_service_account_id = ex_service_account.id
      aesa_dao.insert(account_ex_service_account)
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

		### XML生成
		require 'rexml/document'
		
		# XML生成
		xml = REXML::Document.new
		xml << REXML::XMLDecl.new('1.0', 'UTF-8')
		
		# account 要素生成
		root = xml.add_element('account_profile')
		
		account_e = root.add_element('account')
		account_e.add_element('name').add_text(account.name)
		
		# profile 要素生成
		profile_e = account_e.add_element('profile')
		profile_e.add_element('id').add_text(account_profile_id.to_i.to_s)
		profile_e.add_element('is_unique').add_text(profile_property.is_unique.to_i.to_s)
		
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
