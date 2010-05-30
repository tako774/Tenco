#!/usr/bin/ruby
# -*- coding: utf-8 -*-

# 開始時刻
now = Time.now

### Glicko Ratings 更新 (ファイル入力) ###
REVISION = '0.01'
DEBUG = 1

$LOAD_PATH.unshift '../common'
$LOAD_PATH.unshift '../entity'
$LOAD_PATH.unshift '../dao'

require 'kconv'
require 'yaml'
require 'time'

require 'db'
require 'utils'
include Utils

source = ""

# ログファイルパス
LOG_PATH = "../log/rating_#{now.strftime('%Y%m%d')}.log"
ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

# データファイルディレクトリ
DATA_DIR = "../dat/ratings"

# HTTP/HTTPSレスポンス文字列
res_status = ''
res_header = ''
res_body = "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}\n"

begin
	# 設定
	games = nil # レート計算対象ゲーム情報
	
	CSV_SEPARATOR = ','
	CSV_SEPARATOR_REGEX = /,/o
	
	# DB接続
	db = DB.getInstance()
	db.exec("BEGIN TRANSACTION")
	
	res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	# 処理対象のゲームID取得
	require 'GameDao'
	game_dao = GameDao.new
	games = game_dao.get_rating_targets
	
	res_body << "batch target games selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	# ゲームIDごとにレート計算実行
	games.each do |game|
		res_body << "★GAME_ID:#{game.id} の処理\n"
		
		data_file = "#{DATA_DIR}/#{game.id}"
		update_sql = ""
		insert_sql = ""
		
		# レート情報をファイルから読み込みDBに保存
		File.open(data_file, 'rb') do |io|
			while (line = io.gets) do
				account_id,
				type1_id,
				rate,
				rd,
				matched_accounts,
				matched_counts = line.chop!.split(CSV_SEPARATOR_REGEX)
				
				begin
					# UPDATE or INSERT
					update_sql = <<-"SQL"
						UPDATE
						  game_account_ratings
						SET
						  rating = #{rate.to_f},
						  ratings_deviation = #{rd.to_f},
						  matched_accounts = #{matched_accounts.to_i},
						  match_counts = #{matched_counts.to_i},
						  updated_at = CURRENT_TIMESTAMP,
						  lock_version = lock_version + 1
						WHERE
						  game_id = #{game.id.to_i}
						  AND account_id = #{account_id.to_i}
						  AND type1_id = #{type1_id.to_i}
					SQL
								
					res_update = db.exec(update_sql)
												
					# UPDATE 失敗時は INSERT
					if res_update.cmdstatus != 'UPDATE 1' then
						insert_sql = <<-"SQL"
						INSERT INTO
						  game_account_ratings
						  (
							game_id,
							account_id,
							type1_id,
							rating,
							ratings_deviation,
							matched_accounts,
							match_counts
						  )
						  VALUES
						  (
							#{game.id.to_i},
							#{account_id.to_i},
							#{type1_id.to_i},
							#{rate.to_f},
							#{rd.to_f},
							#{matched_accounts.to_i},
							#{matched_counts.to_i}
						  )
						SQL
						
						db.exec(insert_sql)
					end
								
					res_update.clear
					
				rescue => ex
					res_status = "Status: 500 Server Error\n"
					res_body << "レーティング情報保存時にエラーが発生しました。\n#{update_sql}\n#{insert_sql}"
					raise ex
				end
					
				
			end
		end
		
		res_body << "rating results stored...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	end
	
	# コミット
	db.exec("COMMIT")
	res_body << "transaction finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	# DB ANALYZE
	# GameAccountRating.connection.execute("VACUUM ANALYZE;")
	# res_body << "DB analyzed...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
rescue => ex
	res_status = "Status: 500 Server Error\n" unless res_status
	res_body << "レーティング計算時にエラーが発生しました。ごめんなさい。（#{now.to_s}）\n"
	File.open(ERROR_LOG_PATH, 'a') do |log|
		log.puts "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}"
		log.puts source
		log.puts ex.to_s
		log.puts ex.backtrace.join("\n").to_s
		log.puts
	end
else
	res_status = "Status: 200 OK\n" unless res_status
	res_body << "レーティング計算正常終了。\n"
ensure
	# DB接続を閉じる
	db.close if db
end

# 実行時間
times = Process.times
res_body << "実行時間 #{Time.now - now}秒, CPU時間 #{times.utime + times.stime}秒\n"
	
# HTTP レスポンス送信
res_status = "Status: 500 Internal Server Error\n" unless res_status
res_header = "content-type:text/plain; charset=utf-8\n"
if ENV['REQUEST_METHOD'] == 'GET' then
	print res_status
	print res_header
	print "\n"
end
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
