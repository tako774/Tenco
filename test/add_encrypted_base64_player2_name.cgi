#!/usr/bin/ruby

# 開始時刻
now = Time.now

### track_records.encrypted_base64_player2_account を入れる ###
REVISION = '0.01'
DEBUG = 1

$LOAD_PATH.unshift '../common'
$LOAD_PATH.unshift '../entity'

require 'kconv'
require 'yaml'
require 'time'

require 'db'
require 'utils'
include Utils
require 'cryption'

source = ""

# ログファイルパス
LOG_PATH = "../log/rating_#{now.strftime('%Y%m%d')}.log"
ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

# HTTP/HTTPSレスポンス文字列
res_status = ''
res_header = ''
res_body = "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}\n"

if ENV['REQUEST_METHOD'] == 'GET' then
	begin

		query = {} # クエリストリング
		track_records = [] # 対戦結果
		account_data_passwords = {} # アカウントIDごとのデータパスワード
		
		# クエリストリング分解
		ENV['QUERY_STRING'].to_s.split(/[;&]/).each do |q|
		  key, val = q.split(/=/, 2)
		  query[key] = val.gsub(/\+/," ").gsub(/%[a-fA-F\d]{2}/){ $&[1,2].hex.chr } if val
		end
		
		# クエリ取得
		offset = query['offset']
		limit = query['limit']
		res_body << %!#{"OFFSET " + offset + "\n"}! if offset 
		res_body << %!#{"LIMIT " + limit + "\n"}! if limit
		
		# DB接続
		require 'db'
		db = DB.getInstance()
		db.exec("BEGIN TRANSACTION")
		
		res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# 対戦結果データ取得
		res = db.exec(<<-"SQL")
			SELECT
			  id,
			  data_password
			FROM
			  accounts
			SQL
		
		res.each do |r|
			account_data_passwords[r[0]] = r[1]
		end
		res.clear
		
		res_body << "account_data_passwords selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		require 'TrackRecord'
		res = db.exec(<<-"SQL")
			SELECT
				id,
				player1_account_id,
				player2_name
			FROM
				track_records
			WHERE
				encrypted_base64_player2_name IS NULL
			ORDER BY
				id
			#{"OFFSET " + offset if offset} #{"LIMIT " + limit if limit}
		SQL
		
		if res.num_tuples == 0 then
			raise "対象レコードがありません"
		end
		
		res.each do |r|
			t = TrackRecord.new
			t.id = r[0]
			t.player1_account_id = r[1]
			t.player2_name = r[2]
			track_records << t
		end
		res.clear
		
		res_body << "trackrecords selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
				
		# 計算結果をDBに保存
		begin
			track_records.each do |t|
			
				# 更新または作成
				res_update = db.exec(<<-"SQL")
					UPDATE
					  track_records
					SET
					  encrypted_base64_player2_name = #{s Cryption.encrypt_base64(t.player2_name.to_s, account_data_passwords[t.player1_account_id])}
					WHERE
					  id = #{t.id.to_i}
				SQL
			end
				
		rescue => ex
			res_status = "Status: 500 Server Error\n"
			res_body << "エラー\n"
			raise ex
		else
			res_body << "正常に実行しました。\n"
		end
		
		res_body << "stored...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# コミット
		db.exec("COMMIT")
		res_body << "transaction finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# DB ANALYZE
		db.exec("VACUUM track_records")
		res_body << "DB vacuumed...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
	rescue => ex
		res_status = "Status: 500 Server Error\n" unless res_status
		res_body << "エラーが発生しました。ごめんなさい。（#{now.to_s}）\n"
		File.open(ERROR_LOG_PATH, 'a') do |log|
			log.puts "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}"
			log.puts source
			log.puts ex.to_s
			log.puts ex.backtrace.join("\n").to_s
			log.puts
		end
	else
		res_status = "Status: 200 OK\n" unless res_status
		res_body << "正常終了。\n"
	ensure
		# DB接続を閉じる
		db.close if db
	end
else
	res_status = "Status: 400 Bad Request\n"
	res_body = "400 Bad Request\n"
end

# 実行時間
times = Process.times
res_body << "実行時間 #{Time.now - now}秒, CPU時間 #{times.utime + times.stime}秒"
	
# HTTP レスポンス送信
res_status "Status: 500 Internal Server Error\n" unless res_status
res_header = "content-type:text/plain; charset=utf-8\n"
print res_status
print res_header
print "\n"
print res_body

# ログ書き込み
File.open(LOG_PATH, 'a') do |log|
	log.puts "#{now.iso8601} #{File::basename(__FILE__)} Rev.#{REVISION}"
	log.puts "Total Time: #{Time.now - now}"
	log.puts res_status
	log.puts res_header
	log.puts "\n"
	log.puts res_body
	log.puts "----"
end

exit
