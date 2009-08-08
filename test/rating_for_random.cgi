#!/usr/bin/ruby

### Type1 ランダムのレート計算 ###
begin

# 開始時刻
now = Time.now

REVISION = '0.04'
DEBUG = 1

TOP_DIR = '..'

$LOAD_PATH.unshift "#{TOP_DIR}/common"
$LOAD_PATH.unshift "#{TOP_DIR}/entity"
$LOAD_PATH.unshift "#{TOP_DIR}/dao"

require 'time'
require 'logger'
require 'utils'
include Utils
require 'db'
require 'segment_const'

# ログファイルパス
LOG_PATH = "../log/rating_#{now.strftime('%Y%m%d')}.log"
ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

# HTTP/HTTPSレスポンス文字列
res_status = ''
res_header = ''
res_body = "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}\n"

# 引数
source = ''

rescue
	print "Status: 500 Internal Server Error\n"
	print "content-type: text/plain\n\n"
	print "サーバーエラーです。ごめんなさい。(Initialize Error #{Time.now.strftime('%Y/%m/%d %H:%m:%S')})"
	#print ex.to_s
	#print ex.backtrace.join("\n").to_s
end

begin
	# 設定
	game_id = 1
	
	# 変数
	min_matched_accounts = 5 # マッチ済みアカウント数の最小値
	
	# DB接続
	db = DB.getInstance
	# トランザクション開始
	db.exec("BEGIN TRANSACTION")
	
	res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

	# 処理対象のゲームID取得
	require 'GameDao'
	game_dao = GameDao.new
	game_ids = game_dao.get_batch_target_ids
		
	res_body << "batch target game_ids selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	# ゲームIDごとにレート処理実行
	game_ids.each do |game_id|
		res_body << "★GAME_ID:#{game_id} の処理\n"

		game_account_ratings = {} # レーティング情報
		game_account_random_ratings = [] # Type1ランダムレーティング情報
		max_type1_id = nil # Type1 の最大値
		min_type1_id = nil # Type1 の最小値
		
		res_body << "Type1 random ratings update started...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# Type1 の範囲を取得
		res = db.exec(<<-"SQL")
			SELECT
			  MAX(type1_id),
			  MIN(type1_id)
			FROM
			  game_type1s
			WHERE
			  game_id = #{game_id.to_i}
		SQL

		max_type1_id = res[0][0].to_i
		min_type1_id = res[0][1].to_i
		type1_id_counts = max_type1_id - min_type1_id + 1
		res.clear
		
		# 全Type1のレート情報をもつアカウントのレート情報を取得
		require 'GameAccountRating'
		res = db.exec(<<-"SQL")
			SELECT 
			  r1.*
			FROM
			  game_account_ratings r1,
			  (
				SELECT
				  r2.game_id AS game_id, r2.account_id AS account_id, COUNT(r2.id) AS count
				FROM
				  game_account_ratings r2, accounts a
				WHERE
				  game_id = #{game_id.to_i}
				  AND r2.account_id = a.id
				  AND a.del_flag = 0
				  AND r2.type1_id >= #{min_type1_id}
				  AND r2.type1_id <= #{max_type1_id}
				  AND r2.matched_accounts >= #{min_matched_accounts}
				GROUP BY
				  r2.game_id, r2.account_id
			  ) counts
			WHERE
			  counts.count = #{type1_id_counts}
			  AND r1.game_id = counts.game_id
			  AND r1.account_id = counts.account_id
			  AND r1.type1_id >= #{min_type1_id}
			  AND r1.type1_id <= #{max_type1_id}
		SQL
		
		res.each do |r|
			gar = GameAccountRating.new
			res.num_fields.times do |i|
				gar.instance_variable_set("@#{res.fields[i]}", r[i])
			end
			game_account_ratings[gar.account_id.to_i] ||= {}
			game_account_ratings[gar.account_id.to_i][gar.type1_id.to_i] = gar
		end
		res.clear
		
		res_body << "#{game_account_ratings.length} 件のレーティング情報を取得。\n"
		res_body << "game account ratings selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# Type1ランダムレート情報生成
		game_account_ratings.each do |account_id, gars|
			game_account_random_rating = GameAccountRating.new
			game_account_random_rating.game_id = game_id.to_i
			game_account_random_rating.account_id = account_id.to_i
			game_account_random_rating.type1_id = SEG_V[:virtual_type1][:random][:value].to_i
			
			sum_matched_accounts = 0
			sum_match_counts = 0
			sum_ratings = 0.0
			avg_ratings = 0.0
			rv = 0.0
			rd = 0.0
			
			# マッチ済み試合数・マッチ済みアカウント数・合計レート
			gars.each do |type1_id, gar|
				sum_match_counts += gar.match_counts.to_i
				sum_matched_accounts += gar.matched_accounts.to_i
				sum_ratings += gar.rating.to_f
			end
			# 平均レート
			avg_ratings = sum_ratings.to_f / type1_id_counts.to_f
			
			# ランダムでのRD
			gars.each do |type1_id, gar|
				rv += gar.ratings_deviation.to_f ** 2.0
				rv += (gar.rating.to_f - avg_ratings.to_f) ** 2.0
			end
			rd = (rv.to_f / type1_id_counts.to_f) ** 0.5
			
			game_account_random_rating.match_counts = sum_match_counts
			game_account_random_rating.matched_accounts = sum_matched_accounts
			game_account_random_rating.rating = avg_ratings
			game_account_random_rating.ratings_deviation = rd
			
			game_account_random_ratings << game_account_random_rating
		end
		
		res_body << "Type1ランダムでのレート計算を取得。\n"
		res_body << "Type1 random ratings calculated...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# 結果をDBに保存
		begin
			game_account_random_ratings.each do |gar|
				
				# 更新または作成。クラスが変わらない場合、時刻は更新しない。
				res_update = db.exec(<<-"SQL")
					UPDATE
					  game_account_ratings
					SET
					  match_counts = #{gar.match_counts.to_i},
					  matched_accounts = #{gar.matched_accounts.to_i},
					  rating = #{gar.rating.to_f},
					  ratings_deviation = #{gar.ratings_deviation.to_f},
					  updated_at = CURRENT_TIMESTAMP,
					  lock_version = lock_version + 1
					WHERE
					  game_id = #{gar.game_id.to_i}
					  AND account_id = #{gar.account_id.to_i}
					  AND type1_id = #{gar.type1_id.to_i}
					RETURNING id
				SQL
								
				# UPDATE 失敗時は INSERT
				if res_update.num_tuples != 1 then
					res_update.clear
					res_insert = db.exec(<<-"SQL")
					  INSERT INTO
						game_account_ratings
						(
						  game_id,
						  account_id,
						  type1_id,
						  match_counts,
						  matched_accounts,
						  rating,
						  ratings_deviation
						)
					  VALUES
						(
						  #{gar.game_id.to_i},
						  #{gar.account_id.to_i},
						  #{gar.type1_id.to_i},
						  #{gar.match_counts.to_i},
						  #{gar.matched_accounts.to_i},
						  #{gar.rating.to_f},
						  #{gar.ratings_deviation.to_f}
						)
					  RETURNING id;
					SQL
					
					if res_insert.num_tuples != 1 then
						res_insert.clear
						raise "UPDATE 失敗後の INSERT に失敗しました。"
					end
					
					res_insert.clear
				else
					res_update.clear
				end
				
			end
			
			
		rescue => ex
			res_status = "Status: 500 Server Error\n"
			res_body << "Type1ランダムレート情報保存時にエラーが発生しました。\n"
			raise ex
		else
			res_body << "Type1ランダムレート情報保存を正常に実行しました。\n"
		end
		
		res_body << "Type1 random ratings stored...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	end
	
	# コミット
	db.exec("COMMIT")
	res_body << "transaction finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	# アナライズ
	# db.exec("VACUUM ANALYZE")
	# res_body << "DB analyzed...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
rescue => ex
	res_status = "Status: 500 Server Error\n" unless res_status
	res_body << "Type1ランダムレート情報更新時にエラーが発生しました。ごめんなさい。（#{now.to_s}）\n"
	File.open(ERROR_LOG_PATH, 'a') do |log|
		log.puts "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}"
		log.puts source
		log.puts ex.to_s
		log.puts ex.backtrace.join("\n").to_s
		log.puts
	end
else
	res_status = "Status: 200 OK\n" unless res_status
	res_body << "Type1ランダムレート情報更新正常終了。\n"
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
