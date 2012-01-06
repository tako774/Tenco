#!/usr/bin/ruby

begin
	# 開始時刻
	now = Time.now

	### 登録済み最終対戦結果時刻出力 API ###
	REVISION = 'R0.11'

	$LOAD_PATH.unshift '../common'

	require 'yaml'
	require 'time'
	require 'logger'
	require 'utils'

	# ログファイルパス
	LOG_PATH = "../log/log_#{now.strftime('%Y%m%d')}.log"
	ACCESS_LOG_PATH = "../log/access_#{now.strftime('%Y%m%d')}.log"
	ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

	# HTTP/HTTPSレスポンス文字列
	res_status = ''
	res_header = ''
	res_body = ""

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

if ENV['REQUEST_METHOD'] == 'GET' then
	begin
		query = {} # クエリストリング
		db = nil   # DB接続 
		last_track_record_timestamp = nil # 最終対戦時刻
		
		# バリデーション用定数
		ID_REGEX = /\A[0-9]+\z/
		ACCOUNT_NAME_REGEX = /\A[a-zA-Z0-9_]+\z/
		
		# クエリストリング分解
		query = parse_query_str(ENV['QUERY_STRING'])
		
		if (
			query['game_id'] and
			query['game_id'] =~ ID_REGEX and
			query['account_name'] and
			query['account_name'] =~ ACCOUNT_NAME_REGEX
		) then
			account_name = query['account_name']  # アカウント名
			game_id = query['game_id'].to_i       # ゲーム番号
			
			# DB接続
			begin
				require 'db'
				db = DB.getInstance
				
				# 登録された対戦記録のうち、play_timestamp が最終のものを取得	
				res = db.exec(<<-"SQL")
					SELECT
						last_play_timestamp
					FROM
						game_accounts ga, accounts a
					WHERE
					      a.name = #{s account_name}
					  AND ga.game_id = #{game_id.to_i}
					  AND ga.account_id = a.id
					  AND a.del_flag = 0
				SQL
				
				if res.num_tuples >= 1 then
					last_track_record_timestamp = res[0][0].to_s
				else
					last_track_record_timestamp = nil
				end
					
			rescue => ex
				res_status = "Status: 500 Server Error\n"
				res_body = "サーバーエラーです。\n"
				raise ex
			ensure
				res.clear if res
				db.close  if db
			end
			
			# レスポンス作成
			if (last_track_record_timestamp && last_track_record_timestamp != '') then
				res_status "Status: 200 OK\n" unless res_status
				res_body = Time.parse(last_track_record_timestamp).iso8601
			else
				res_status = "Status: 204 No Content\n" unless res_status
			end
		else
			res_status = "Status: 400 Bad Request\n"
			res_body = "400 Bad Request\n"
		end	
	rescue => ex
		res_status = "Status: 500 Server Error\n" unless res_status
		File.open(ERROR_LOG_PATH, 'a') do |err_log|
			err_log.puts "#{DateTime.now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}" 
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

# HTTP レスポンス送信
res_status "Status: 500 Internal Server Error\n" unless res_status
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
			ENV['QUERY_STRING'].gsub(/\r\n|\n/, '\n')[0..99]
		].join("\t")
	)
rescue
end

exit
