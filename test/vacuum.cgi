#!/usr/bin/ruby

# 開始時刻
now = Time.now

### PostgreSQL VACUUM ###
REVISION = 'R0.01'
DEBUG = 1

$LOAD_PATH.unshift '../common'

require 'time'
require 'logger'
require 'utils'
include Utils

# ログファイルパス
LOG_PATH = "../log/VACCUM_#{now.strftime('%Y%m%d')}.log"
ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

# HTTP/HTTPSレスポンス文字列
res_status = "Status: 500 Internal Server Error\n"
res_header = ''
res_body = ""

# ログ開始
log = Logger.new(LOG_PATH)
log.level = Logger::DEBUG

if ENV['REQUEST_METHOD'] == 'GET' then
	begin
		vacuum_sql = nil # VACCUM 依頼SQL文
		
		if ENV['QUERY_STRING'] == 'mode=full'
			vacuum_sql = 'VACUUM FULL ANALYZE'
		else
			vacuum_sql = 'VACUUM ANALYZE'
		end
		
		# DB 接続
		require 'db'
		db = DB.getInstance
		
		res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# バキューム
		res = db.exec(vacuum_sql)
		
		res_body << "#{vacuum_sql} finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
				
	rescue => ex
		res_status = "Status: 500 Server Error\n" unless res_status
		res_body << "バキューム時にエラーが発生しました（#{now.to_s}）\n"		
		File.open(ERROR_LOG_PATH, 'a') do |err_log|
			err_log.puts "#{now.strftime('%Y/%m/%d %H:%M:%S')} #{File::basename(__FILE__)} Rev.#{REVISION}" 
			err_log.puts ENV['QUERY_STRING']
			err_log.puts ex.to_s
			err_log.puts ex.backtrace.join("\n").to_s
			err_log.puts
		end
	else
		res_status = "Status: 200 OK\n"
		res_body << "バキューム完了(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n"
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
