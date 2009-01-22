#!/usr/bin/ruby

### データパスワードを全アカウントに設定 ###

# 開始時刻
now = Time.now
# リビジョン
REVISION = 'R0.01'

DEBUG = 1

# アプリケーションのトップディレクトリ
TOP_DIR = '..'

$LOAD_PATH.unshift "#{TOP_DIR}/common"
$LOAD_PATH.unshift "#{TOP_DIR}/entity"

require 'time'
require 'logger'
require 'utils'
include Utils
require 'db'
require 'cryption'

# TOP ページ URL
TOP_URL = 'http://tenco.xrea.jp/'
# ログファイルパス
LOG_PATH = "#{TOP_DIR}/log/log_#{now.strftime('%Y%m%d')}.log"
ERROR_LOG_PATH = "#{TOP_DIR}/log/error_#{now.strftime('%Y%m%d')}.log"

# HTTP/HTTPSレスポンス文字列
res_status = ''
res_header = ''
res_body = ""

# ログ開始
logger = Logger.new(LOG_PATH)
logger.level = Logger::DEBUG

if ENV['REQUEST_METHOD'] == 'GET' then
	begin
		require 'Account'
		
		db = nil   # DB接続	
		data_password_length = 16  # データパスワードのオクテット文字列長 
		accounts = []  # アカウント
		
		# DB接続
		db = DB.getInstance
		res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

		# トランザクション開始
		db.exec("BEGIN TRANSACTION")		
		
		### ゲーム統計情報取得
		
		# 全アカウント取得
		res = db.exec(<<-"SQL")
		  SELECT
		    id
		  FROM
			accounts
		SQL
		
		res.each do |r|
			a = Account.new
			res.num_fields.times do |i|
				a.instance_variable_set("@#{res.fields[i]}", r[i])
			end
			accounts << a
		end
		res.clear
		
		# 全アカウントの data_password を設定しなおす
		accounts.each do |a|
			res = db.exec(<<-"SQL")
			  UPDATE
			    accounts
			  SET
				data_password = #{s Cryption.mk_octet_str(data_password_length)},
				updated_at = CURRENT_TIMESTAMP,
				lock_version = lock_version + 1
			  WHERE
			    id = #{a.id.to_i}
			  RETURNING *
			SQL
			
			if res.num_tuples < 1 then
				res.clear
				res_status = "Status: 200 OK\n"
				res_body = "アカウント情報の更新に失敗しました（アカウントID：#{a.id.to_i}）\n"
				raise "アカウント情報の更新に失敗しました（アカウントID：#{a.id.to_i}）"
			else
				res.clear
			end
		
		end
		
		res_body << "全アカウントのデータパスワード更新 #{accounts.length} 件\n"
		res_body << "all accounts data_password updated ...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# コミット
		db.exec("COMMIT")
		res_body << "transaction finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# アナライズ
		db.exec("VACUUM ANALYZE")
		res_body << "DB analyzed...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
	rescue => ex
		res_status = "Status: 500 Server Error\n" unless res_status
		res_body << "サーバーエラーです。ごめんなさい。\n"
		res_body << "#{ex.to_s}\n"
		res_body << "#{ex.backtrace.join("\n")}\n"
		File.open(ERROR_LOG_PATH, 'a') do |err_log|
			err_log.puts "#{now.to_s} #{File::basename(__FILE__)} #{REVISION}" 
			err_log.puts ENV['QUERY_STRING']
			err_log.puts ex.to_s
			err_log.puts ex.backtrace.join("\n").to_s
			err_log.puts
		end
	ensure
		db.close if db
	end
else
	res_status = "Status: 400 Bad Request\n"
	res_body = "400 Bad Request\n"
end

res_body << "process finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

begin
# HTTP レスポンス送信
res_status = "Status: 500 Internal Server Error\n" unless res_status
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
			ENV['QUERY_STRING'].gsub(/\r\n|\n/, '\n')[0..99]
		].join("\t")
	)
rescue
end
