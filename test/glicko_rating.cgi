#!/usr/bin/ruby

# 開始時刻
now = Time.now

### Glicko Ratings 計算 ###
REVISION = '0.17'
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

# HTTP/HTTPSレスポンス文字列
res_status = ''
res_header = ''
res_body = "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}\n"

begin
	# 設定
	INIT_RATE = 1500.0 # 初期レート
	MIN_RD = 50.0      # Ratings Deviation の最小値
	MAX_RD = 350.0     # Ratings Deviation の最大値
	MIN_RD_SQ = MIN_RD ** 2.0 # Ratings Deviation の最小値の２乗
	MAX_RD_SQ = MAX_RD ** 2.0 # Ratings Deviation の最大値の２乗
	RD_SATURATION_TIME = 365.2422 * 24 * 60 * 60  # RD が時間経過で最小から最大まで飽和するまでの秒数
	RD_DEC = (MAX_RD ** 2.0 - MIN_RD ** 2.0) / RD_SATURATION_TIME.to_f  # RD の時間経過に伴う逓減係数
	Q = Math::log(10) / 400.0 # 定数
	QIP = 3.0 * ((Q / Math::PI) ** 2) # 定数 
	B = 10.0 ** (1.0/400.0) # 定数 
	INV_B = 10.0 ** (-1.0/400.0)  # 定数 
	
	
	# DB接続
	require 'db'
	db = DB.getInstance()
	db.exec("BEGIN TRANSACTION")
	
	res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	# 処理対象のゲームID取得
	require 'GameDao'
	game_dao = GameDao.new
	game_ids = game_dao.get_batch_target_ids
		
	res_body << "batch target game_ids selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	# ゲームIDごとにレート計算実行
	game_ids.each do |game_id|
		res_body << "★GAME_ID:#{game_id} の処理\n"
		
		account_type1_rate = {} # アカウント・キャラごとのレート情報
		
		# 対戦結果データ取得
		require 'TrackRecord'
		res = db.exec(<<-"SQL")
			SELECT
			  rep_timestamp,
			  player1_account_id,
			  player2_account_id,
			  player1_type1_id,
			  player2_type1_id,
			  player1_points,
			  player2_points
			FROM
			  track_records			
			WHERE
				  id > matched_track_record_id
			  AND game_id = #{game_id.to_i}
			ORDER BY
			  rep_timestamp
			SQL
			
		res_body << "matched trackrecords selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

		# 以下ループで使いまわすインスタンス
		t = TrackRecord.new
		
		res.each do |r|
			# 高速化のためインスタンス変数名直接指定
			# また、型変換をしておく
			t.rep_timestamp = pgsql_timestamp_str_to_time(r[0])
			t.player1_account_id = r[1]
			t.player2_account_id = r[2]
			t.player1_type1_id = r[3]
			t.player2_type1_id = r[4]
			t.player1_points = r[5].to_i
			t.player2_points = r[6].to_i
#		res.num_fields.times do |i|
#			t.instance_variable_set("@#{res.fields[i]}", r[i])
#		end
			
			### 発生時間順にレート計算
			
			# アカウント・タイプ別レート情報初期化
			account_type1_rate[t.player1_account_id] ||= {}
			account_type1_rate[t.player2_account_id] ||= {}
			account_type1_rate[t.player1_account_id][t.player1_type1_id] ||= 
				{
					:rate => INIT_RATE,
					:rd_sq => MAX_RD_SQ,
					:last_timestamp => t.rep_timestamp,
					:account_ids => [],
					:counts => 0
				}
			account_type1_rate[t.player2_account_id][t.player2_type1_id] ||=
				{
					:rate => INIT_RATE,
					:rd_sq => MAX_RD_SQ,
					:last_timestamp => t.rep_timestamp,
					:account_ids => [],
					:counts => 0
				}
			
			# ハッシュオブジェクトキャッシュ
			player1_type1_rate = account_type1_rate[t.player1_account_id][t.player1_type1_id]
			player2_type1_rate = account_type1_rate[t.player2_account_id][t.player2_type1_id]
			
			# 対戦前レート情報取得
			rate1         = player1_type1_rate[:rate]
			rd1_sq        = player1_type1_rate[:rd_sq]
			elapsed_time1 = t.rep_timestamp - player1_type1_rate[:last_timestamp]
			rate2         = player2_type1_rate[:rate]
			rd2_sq        = player2_type1_rate[:rd_sq]
			elapsed_time2 = t.rep_timestamp - player2_type1_rate[:last_timestamp]

			# 対戦結果取得
			point1 = (1.0 + (t.player1_points <=> t.player2_points)) * 0.5
			point2 = 1.0 - point1
			
			### レート計算
			
			# RD の２乗の時間経過による上昇
			rd1_sq = rd1_sq + RD_DEC * elapsed_time1
			rd1_sq = MAX_RD_SQ if rd1_sq > MAX_RD_SQ
			rd2_sq = rd2_sq + RD_DEC * elapsed_time2
			rd2_sq = MAX_RD_SQ if rd2_sq > MAX_RD_SQ
			
			# 信頼度による影響低下係数
			g_rd1 = (1.0 + QIP * rd1_sq) ** (-0.5)
			g_rd2 = (1.0 + QIP * rd2_sq) ** (-0.5)
			#g_rd1 = (1.0 + 3.0 * ((Q * rd1 / Math::PI) ** 2.0)) ** (-0.5)
			#g_rd2 = (1.0 + 3.0 * ((Q * rd2 / Math::PI) ** 2.0)) ** (-0.5)
			
			# 勝利期待値
			b_d_rate = B ** (rate2 - rate1)
			expected_point1 = 1.0 / (1.0 + b_d_rate ** g_rd2)
			g_rd1_b_d_rate  = b_d_rate ** g_rd1
			expected_point2 = g_rd1_b_d_rate / (1.0 + g_rd1_b_d_rate)
			# expected_point1 = 1.0 / (1.0 + 10.0 ** (g_rd2 * (rate2 - rate1) * 0.0025))
			# expected_point2 = 1.0 / (1.0 + 10.0 ** (g_rd1 * (rate1 - rate2) * 0.0025))

			# レート変化の分散の逆数
			d1_inv_sq = ((Q * g_rd2) ** 2) * expected_point1 * (1.0 - expected_point1)
			d2_inv_sq = ((Q * g_rd1) ** 2) * expected_point2 * (1.0 - expected_point2)

			# 対戦後RD の２乗
			rd1_sq = 1.0 / (1.0 / rd1_sq + d1_inv_sq)
			rd1_sq = MIN_RD_SQ if rd1_sq < MIN_RD_SQ
			rd2_sq = 1.0 / (1.0 / rd2_sq + d2_inv_sq)
			rd2_sq = MIN_RD_SQ if rd2_sq < MIN_RD_SQ
			
			# 対戦後レート
			rate1 += (Q * rd1_sq) * g_rd2 * (point1 - expected_point1)
			rate2 += (Q * rd2_sq) * g_rd1 * (point2 - expected_point2)
			
			# 計算後レート情報保存
			player1_type1_rate[:rate] = rate1
			player1_type1_rate[:rd_sq] = rd1_sq
			player1_type1_rate[:last_timestamp] = t.rep_timestamp
			player2_type1_rate[:rate] = rate2
			player2_type1_rate[:rd_sq] = rd2_sq
			player2_type1_rate[:last_timestamp] = t.rep_timestamp
			
			# 対戦アカウント保存
			player1_type1_rate[:account_ids] << t.player2_account_id
			player2_type1_rate[:account_ids] << t.player1_account_id

			# 対戦数保存
			player1_type1_rate[:counts] += 1
			player2_type1_rate[:counts] += 1
			
		end

		res_body << "#{res.num_tuples} 件の対戦結果をレート計算対象として取得。\n"

		res.clear
		t = nil
		
		res_body << "ratings calculated...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# 現在のRDを算出
		account_type1_rate.each do |account_id, type1_rate|
			type1_rate.each do |type1_id, rate_info|
				rate_info[:rd_sq] = rate_info[:rd_sq] + RD_DEC * (now - rate_info[:last_timestamp])
				rate_info[:rd_sq] = MAX_RD_SQ if rate_info[:rd_sq] > MAX_RD_SQ
				rate_info[:rd] = rate_info[:rd_sq] ** 0.5
			end
		end
		
		res_body << "RD calculated...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# レート平均を INIT_RATE に合わせる
		sum = 0
		num = 0
		avg = 0
		dif_avg = 0 # (目標平均レート - 平均レート)
		account_type1_rate.each do |account_id, type1_rate|
			type1_rate.each do |type1_id, rate_info|
				sum += rate_info[:rate]
				num += 1
			end
		end
		
		res_body << "ratings avarage calculated...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		avg = sum.to_f / num.to_f
		dif_avg = INIT_RATE - avg
		account_type1_rate.each do |account_id, type1_rate|
			type1_rate.each do |type1_id, rate_info|
				rate_info[:rate] += dif_avg
			end
		end
		
		res_body << "レート平均を #{avg} から #{INIT_RATE} に調整しました。\n"
		sum = num = avg = dif_avg = nil
		
		res_body << "ratings avarage adjusted...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# 計算結果をDBに保存
		begin
			require 'GameAccountRating'
			update_sql = ""
			insert_sql = ""

			account_type1_rate.each do |account_id, type1_rate|
				type1_rate.each do |type1_id, rate_info|
				
					# 更新または作成
					update_sql = <<-"SQL"
UPDATE
  game_account_ratings
SET
  rating = #{rate_info[:rate].to_f},
  ratings_deviation = #{rate_info[:rd].to_f},
  matched_accounts = #{rate_info[:account_ids].uniq.length},
  match_counts = #{rate_info[:counts].to_i},
  updated_at = CURRENT_TIMESTAMP,
  lock_version = lock_version + 1
WHERE
  game_id = #{game_id.to_i}
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
							#{game_id.to_i},
							#{account_id.to_i},
							#{type1_id.to_i},
							#{rate_info[:rate].to_f},
							#{rate_info[:rd].to_f},
							#{rate_info[:account_ids].uniq.length},
							#{rate_info[:counts].to_i}
						  )
						SQL
						
						db.exec(insert_sql)
					end
					
					res_update.clear
				end
			end
			
		rescue => ex
			res_status = "Status: 500 Server Error\n"
			res_body << "レーティング計算時にエラーが発生しました。\n#{update_sql}\n#{insert_sql}"
			raise ex
		else
			res_body << "レーティング計算を正常に実行しました。\n"
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
