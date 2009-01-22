#!/usr/bin/ruby

# 開始時刻
now = Time.now

### 登録済み最終対戦結果時刻出力 API ###
REVISION = 'R0.06'

$LOAD_PATH.unshift '../common'
$LOAD_PATH.unshift '../model'

require 'yaml'
require 'time'
require 'logger'

# ログファイルパス
LOG_PATH = "../log/log_#{now.strftime('%Y%m%d')}.log"
ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

# HTTP/HTTPSレスポンス文字列
res_status = ''
res_header = ''
res_body = ""

# ログ開始
log = Logger.new(LOG_PATH)
log.level = Logger::DEBUG

if ENV['REQUEST_METHOD'] == 'GET' then
	begin
		query = {} # クエリストリング
		db = nil   # DB接続 
		
		# クエリストリング分解
		ENV['QUERY_STRING'].to_s.split(/[;&]/).each do |q|
			key, val = q.split(/=/, 2)
			query[key] = val.gsub(/\+/," ").gsub(/%[a-fA-F\d]{2}/){ $&[1,2].hex.chr } if val
		end
		
		if (query['game_id'] and query['game_id'] !='' and query['account_name'] and query['account_name'] != '') then
			account_name = query['account_name']  # アカウント名
			game_id = query['game_id'].to_i       # ゲーム番号
			
			# DB接続
			begin
				require 'db'
				db = DB.getInstance
				
				# 登録された対戦記録のうち、play_timestamp が最終のものを取得	
				db.con.exec(<<-"SQL")
				PREPARE p (text, int) AS
					SELECT
						MAX(t.play_timestamp)
					FROM
						accounts a, track_records t
					WHERE
					      a.name = $1
					  AND t.game_id = $2
					  AND a.id = t.player1_account_id
					  AND a.del_flag = 0
				SQL
				
				res = db.con.exec("EXECUTE p (E\'#{account_name}\', #{game_id})")
				
				last_track_record_timestamp = res[0][0]
				
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
