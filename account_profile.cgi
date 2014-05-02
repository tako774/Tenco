#!/usr/bin/ruby

# アカウントプロフィール設定ページCGI
begin
	# 開始時刻
	now = Time.now
	# リビジョン
	REVISION = 'R0.01'
	DEBUG = false

	$LOAD_PATH.unshift "#{File.expand_path(File.dirname(__FILE__))}/common"
	$LOAD_PATH.unshift "#{File.expand_path(File.dirname(__FILE__))}/entity"
	$LOAD_PATH.unshift "#{File.expand_path(File.dirname(__FILE__))}/dao"

	require 'db'
	require 'time'
	require 'logger'
	require 'utils'
	require 'setting'
	require 'erubis'
	include Erubis::XmlHelper
	
	require 'ProfilePropertyDao'
	
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
	
	# キャッシュフォルダパス
	CACHE_DIR = "#{TOP_DIR}/cache/#{File::basename(__FILE__)}"
	# キャッシュロックフォルダパス
	CACHE_LOCK_DIR = "#{TOP_DIR}/cache/lock/#{File::basename(__FILE__)}"
	# キャッシュをつかったかどうか
	is_cache_used = false
	# 最大受付POSTデータサイズ（byte）
	MAX_POST_DATA_BYTES = 10000;
	# バリデーション用定数
	ACCOUNT_NAME_REGEX = /\A[a-zA-Z0-9_]+\z/
	VALUE_MAX_LENGTH = 16
	ACCOUNT_PROFILE_COUNT_MAX = 50
	MAX_URI_BYTES = 255
	
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
									
		account_name = nil # 入力アカウント名
		account = nil # アカウント情報
		game_accounts = [] # ゲームアカウント情報
		profile_properties = [] # プロファイルプロパティ情報

		FOOTER_ERB_PATH = "./footer.erb" # フッターERBパス
		LINK_ERB_PATH = "./link.erb" # リンクERBパス

		# DB接続取得
		db = DB.getInstance
		
		# クエリストリング分解・取得
		query = parse_query_str(ENV['QUERY_STRING'])
				
		# 入力バリデーション
		unless (
			query['account_name'] and
			query['account_name'] =~ ACCOUNT_NAME_REGEX
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "入力データが正しくありません\ninput data validation error.\n"
			raise "input data validation error."
		else
			account_name = query['account_name']
		end
	
		# アカウント情報取得
		require 'Account'
		res = db.exec(<<-"SQL")
			SELECT
				id, name
			FROM
				accounts
			WHERE
				name = #{s account_name}
				AND del_flag = 0
		SQL
		
		if res.num_tuples != 1 then
			res.clear
			res_status = "Status: 400 Bad Request\n"
			res_body = "該当アカウントは登録されていません\n"
			raise "該当アカウントは登録されていません"
		else
			account = Account.new
			res.num_fields.times do |i|
				account.instance_variable_set("@#{res.fields[i]}", res[0][i])
			end
			res.clear	
		end
		
		# 該当アカウントのゲームごとの情報を取得
		require 'GameAccount'
		res = db.exec(<<-"SQL")
			SELECT
				ga.*, g.name AS game_name
			FROM
				game_accounts ga,
				games g
			WHERE
				account_id = #{account.id.to_i}
				AND g.id = ga.game_id
			ORDER BY
				g.id
			SQL
		
		res.each do |r|
			game_account = GameAccount.new
			res.num_fields.times do |i|
				game_account.instance_variable_set("@#{res.fields[i]}", r[i])
			end
			game_accounts << game_account
		end
		res.clear
		
		# プロファイルプロパティ情報を取得
		pp_dao = ProfilePropertyDao.new
		profile_properties = pp_dao.get_all
		
		# リンク 部生成
		link_html = Erubis::Eruby.new(File.read(LINK_ERB_PATH)).result(binding)
		# footer 部生成
		footer_html = Erubis::Eruby.new(File.read(FOOTER_ERB_PATH)).result(binding)		
		
		# HTMLページ生成
		html = Erubis::Eruby.new(File.read("#{File::basename(__FILE__, '.*')}.erb")).result(binding)
		
		### 結果をセット
		res_status = "Status: 200 OK\n"
		res_header = "Content-Type:text/html; charset=utf-8\n"
		res_body = html
			
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

