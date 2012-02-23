#!/usr/bin/ruby

# 開始時刻
begin
now = Time.now

### レートランキングデータ作成処理 ###
REVISION = '0.04'
DEBUG = 1

# アプリケーションのトップディレクトリ
TOP_DIR = '..'

$LOAD_PATH.unshift "#{TOP_DIR}/common"
$LOAD_PATH.unshift "#{TOP_DIR}/entity"
$LOAD_PATH.unshift "#{TOP_DIR}/dao"

require 'time'
require 'logger'
require 'utils'
require 'db'

source = ""

# ログファイルパス
LOG_PATH = "../log/rating_#{now.strftime('%Y%m%d')}.log"
ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

# HTTP/HTTPSレスポンス文字列
res_status = ''
res_header = ''
res_body = "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}\n"

rescue
	print "Status: 500 Internal Server Error\n"
	print "content-type: text/plain\n\n"
	print "サーバーエラーです。ごめんなさい。(Initialize Error #{Time.now.strftime('%Y/%m/%d %H:%m:%S')})"
	#print ex.to_s
	#print ex.backtrace.join("\n").to_s
end

begin
	# 設定
	LIMIT_MAX_RD = 150 # ランキング対象の最大RD
	LIMIT_MIN_MATCHED_ACCOUNTS = 20 # ランキング対象の最小マッチ済対戦アカウント人数
		
	# DB 接続
	require 'db'
	db = DB.getInstance
	
	# トランザクション開始
	db.exec("BEGIN TRANSACTION")
	
	res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

	# 処理対象のゲームID取得
	require 'GameDao'
	game_dao = GameDao.new
	game_ids = game_dao.get_batch_target_ids
		
	res_body << "batch target game_ids selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	# ゲームIDごとに処理実行
	game_ids.each do |game_id|
		res_body << "★GAME_ID:#{game_id} の処理\n"
	
		# ランクデータ
		game_account_ratings = [] # ランク対象のレート情報レコード
	
		# ゲーム全体のレート情報を、レート降順（順位順）で取得
		require 'GameAccountRating'
		res = db.exec(<<-"SQL")
			SELECT 
			  r.*
			FROM 
			  accounts a, game_account_ratings r
			WHERE
				  a.id = r.account_id
			  AND r.game_id = #{game_id.to_i}
			  AND a.del_flag = 0
			  AND a.show_ratings_flag != 0
			  AND r.ratings_deviation < #{LIMIT_MAX_RD.to_i}
			  AND r.matched_accounts >= #{LIMIT_MIN_MATCHED_ACCOUNTS.to_i}
			ORDER BY
			  r.rating DESC
		SQL
		
		res_body << "#{res.num_tuples} 件のレート情報を取得。\n"
		res_body << "game account rating info selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		res.each do |r|
			gar = GameAccountRating.new
			res.num_fields.times do |i|
				gar.instance_variable_set("@#{res.fields[i]}", r[i])
			end
			game_account_ratings << gar
		end
		
		# レートランキング情報を取得
		rank_value = 1
		game_account_ratings.each do |gar|
			# ゲーム全体レートランキング情報更新
			gar.game_type1_ratings_rank = rank_value
			rank_value += 1
		end
		rank_value = nil
		
		# キャラ別レートランク情報を取得
		rank_value = {}
		game_account_ratings.each do |gar|
			
			# 該当アカウントのキャラ別レートランキング情報更新
			rank_value[gar.type1_id.to_i] ||= 1
			
			# キャラ別レートランキング情報取得
			gar.game_each_type1_ratings_rank = rank_value[gar.type1_id.to_i]
			rank_value[gar.type1_id.to_i] += 1
			
		end
		rank_value = nil
		
		res_body << "ratings rank calculated...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# 計算結果をDBに保存
		begin
			# 更新
			game_account_ratings.each do |gar|
				db.exec(<<-"SQL")
					UPDATE
					  game_account_ratings
					SET
					  game_type1_ratings_rank = #{gar.game_type1_ratings_rank},
					  game_each_type1_ratings_rank = #{gar.game_each_type1_ratings_rank},
					  updated_at = CURRENT_TIMESTAMP,
					  lock_version = lock_version + 1
					WHERE
					  id = #{gar.id.to_i}
					  AND (
					    game_type1_ratings_rank != #{gar.game_type1_ratings_rank}
					    OR game_each_type1_ratings_rank != #{gar.game_each_type1_ratings_rank}
					  )
				SQL
			end
			
			# ランク外となったランキングデータをクリア
			db.exec(<<-SQL)
				UPDATE
				  game_account_ratings
				SET
				  game_type1_ratings_rank = 0,
				  game_each_type1_ratings_rank = 0,
				  updated_at = CURRENT_TIMESTAMP,
				  lock_version = lock_version + 1
				WHERE
					id IN(
						SELECT
							gar.id
						FROM
							accounts a,
							game_account_ratings gar
						WHERE
							gar.account_id = a.id
							AND gar.game_id = #{game_id.to_i}
							AND (
								NOT (
									a.del_flag = 0
									AND a.show_ratings_flag != 0
									AND gar.ratings_deviation < #{LIMIT_MAX_RD.to_i}
									AND gar.matched_accounts >= #{LIMIT_MIN_MATCHED_ACCOUNTS.to_i}
								)
							)
							AND (
								gar.game_type1_ratings_rank > 0
								OR gar.game_each_type1_ratings_rank > 0
							)
					)
			SQL
				
		rescue => ex
			res_status = "Status: 500 Server Error\n"
			res_body << "レートランキング情報保存時にエラーが発生しました。\n"
			raise ex
		else
			res_body << "レートランキング情報保存を正常に実行しました。\n"
		end
		
		res_body << "rating rankings stored...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	end
			
	# コミット
	db.exec("COMMIT")
	res_body << "transaction finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	# DB ANALYZE
	#db.exec("VACUUM ANALYZE;")
	#res_body << "DB analyzed...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
rescue => ex
	res_status = "Status: 500 Server Error\n" unless res_status
	res_body << "レートランキングデータ作成時にエラーが発生しました。ごめんなさい。（#{now.to_s}）\n"
	File.open(ERROR_LOG_PATH, 'a') do |log|
		log.puts "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}"
		log.puts source
		log.puts ex.to_s
		log.puts ex.backtrace.join("/n").to_s
		log.puts
	end
else
	res_status = "Status: 200 OK\n" unless res_status
	res_body << "レートランキングデータ作成正常終了。\n"
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
