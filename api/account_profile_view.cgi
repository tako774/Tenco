#!/usr/bin/ruby

begin
	# 開始時刻
	now = Time.now

	### アカウントプロフィール(公開分)取得 API ###
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
	
	require 'AccountProfileDao'
	
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

if ENV['REQUEST_METHOD'] == 'GET' then
	begin
		### 変数
		db = nil   # DB接続 
		
		query = {} # クエリストリング
		
		account_name = nil # アカウント名
		account_profiles = [] # アカウントプロフィール情報
		profile_properties = [] # プロフィールプロパティ情報
		profile_classes = {} # クラス別プロフィールプロパティ情報
		
		# クエリストリング分解
		query = parse_query_str(ENV['QUERY_STRING'])
		
		# 値設定
		account_name = query['account_name']

		# 入力バリデーション
		unless (
			account_name and
			account_name =~ ACCOUNT_NAME_REGEX
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "エラー：入力アカウントIDが正しくありません\ninput data validation error.\n"
			raise "input account data validation error."
		end
		
		# DB 接続
		require 'db'
		db = DB.getInstance

		# 公開されているアカウントプロフィール情報を取得
		account_profiles = AccountProfileDao.new.get_by_account_name(account_name, :visibility_check => true)
		
	rescue => ex
		unless res_status then
			res_status ||= "Status: 500 Internal Server Error\n" 
			res_body << "プロフィール情報の取得に失敗しました。サーバーエラーです。\n"
			res_body << "サーバーが不調かもしれません。。。時間をおいてやり直してください。\n"
		end
		File.open(ERROR_LOG_PATH, 'a') do |err_log|
			err_log.puts "#{DateTime.now.to_s} #{File::basename(__FILE__)}"
			err_log.puts ENV['QUERY_STRING']
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
		account_e.add_element('name').add_text(h(account_name))
		
		# profile 要素生成
		account_profiles.each do |ap|
			profile_e = account_e.add_element('profile')
			profile_e.add_element('id').add_text(ap.id.to_i.to_s)
			# CData.new は引数に ']]>' があるとエラーになるが、htmlエスケープしているので発生しない
			profile_e.add_element('name').add_text(h(ap.name))
			profile_e.add_element('display_name').add_text(h(ap.display_name))
			profile_e.add_element('value').add(REXML::CData.new(h(ap.value)))
			profile_e.add_element('uri').add(REXML::CData.new(h(ap.uri)))
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
