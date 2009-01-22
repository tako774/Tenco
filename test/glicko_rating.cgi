#!/usr/bin/ruby

# 開始時刻
now = Time.now

### Glicko Ratings 計算 ###
REVISION = '0.03'
DEBUG = 1

$LOAD_PATH.unshift '../common'
$LOAD_PATH.unshift '../entity'

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

if ENV['REQUEST_METHOD'] == 'GET' then
	begin
		# 設定
		game_id = 1
		INIT_RATE = 1500.0 # 初期レート
		MIN_RD = 50.0      # Ratings Deviation の最小値
		MAX_RD = 350.0     # Ratings Deviation の最大値
		RD_SATURATION_TIME = 365.2422 * 24 * 60 * 60  # RD が時間経過で最小から最大まで飽和するまでの秒数
		RD_DEC = (MAX_RD ** 2.0 - MIN_RD ** 2.0) / RD_SATURATION_TIME.to_f  # RD の時間経過に伴う逓減係数
		Q = Math::log(10) / 400.0 # 定数

		track_records = [] # マッチ済み対戦結果
		account_type1_rate = {} # アカウント・キャラごとのレート情報
		
		# DB接続
		require 'db'
		db = DB.getInstance()
		db.exec("BEGIN TRANSACTION")
		
		res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
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
		
		res.each do |r|
			t = TrackRecord.new
			res.fields.length.times do |i|
				t.instance_variable_set("@#{res.fields[i]}", r[i])
			end
			track_records << t
		end
		
		res_body << "#{track_records.length} 件の対戦結果をレート計算対象として取得。\n"
		res_body << "matched trackrecords selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# 時間変換
		track_records.each do |t|
			t.rep_timestamp =  pgsql_timestamp_str_to_time(t.rep_timestamp)
		end
		
		res_body << "rep_timestamp prased...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# 発生時間順にレート計算
		track_records.each do |t|
			
			# アカウント・タイプ別レート情報初期化
			account_type1_rate[t.player1_account_id] ||= {}
			account_type1_rate[t.player2_account_id] ||= {}
			account_type1_rate[t.player1_account_id][t.player1_type1_id] ||= 
				{
					:rate => INIT_RATE,
					:rd => MAX_RD,
					:last_timestamp => t.rep_timestamp,
					:account_ids => [],
					:counts => 0
				}
			account_type1_rate[t.player2_account_id][t.player2_type1_id] ||=
				{
					:rate => INIT_RATE,
					:rd => MAX_RD,
					:last_timestamp => t.rep_timestamp,
					:account_ids => [],
					:counts => 0
				}
			
			# 対戦前レート情報取得
			rate1         = account_type1_rate[t.player1_account_id][t.player1_type1_id][:rate]
			rd1           = account_type1_rate[t.player1_account_id][t.player1_type1_id][:rd]
			elapsed_time1 = t.rep_timestamp - account_type1_rate[t.player1_account_id][t.player1_type1_id][:last_timestamp]
			rate2         = account_type1_rate[t.player2_account_id][t.player2_type1_id][:rate]
			rd2           = account_type1_rate[t.player2_account_id][t.player2_type1_id][:rd]
			elapsed_time2 = t.rep_timestamp - account_type1_rate[t.player2_account_id][t.player2_type1_id][:last_timestamp]
			
			# 対戦結果取得
			point1 = (1.0 + (t.player1_points.to_i <=> t.player2_points.to_i)) / 2.0
			point2 = (1.0 + (t.player2_points.to_i <=> t.player1_points.to_i)) / 2.0
			
			### レート計算
			
			# RD の時間経過による上昇
			rd1 = [(rd1 ** 2.0 + RD_DEC * elapsed_time1) ** 0.5, MAX_RD].min
			rd2 = [(rd2 ** 2.0 + RD_DEC * elapsed_time2) ** 0.5, MAX_RD].min
			
			# 信頼度による影響低下係数
			g_rd1 = (1.0 + 3.0 * ((Q * rd1 / Math::PI) ** 2.0)) ** (-0.5)
			g_rd2 = (1.0 + 3.0 * ((Q * rd2 / Math::PI) ** 2.0)) ** (-0.5)
			
			# 勝利期待値
			expected_point1 = 1.0 / (1.0 + 10.0 ** (g_rd2 * (rate2 - rate1) / 400.0))
			expected_point2 = 1.0 / (1.0 + 10.0 ** (g_rd1 * (rate1 - rate2) / 400.0))

			# レート変化の分散
			d1 = (((Q * g_rd2) ** 2) * expected_point1 * (1 - expected_point1)) ** (-0.5)
			d2 = (((Q * g_rd1) ** 2) * expected_point2 * (1 - expected_point2)) ** (-0.5)

			# 対戦後RD
			rd1 = [((1 / rd1 ** 2) + (1 / d1 ** 2)) ** (-0.5), MIN_RD].max
			rd2 = [((1 / rd2 ** 2) + (1 / d2 ** 2)) ** (-0.5), MIN_RD].max
			
			# 対戦後レート
			rate1 += (Q * (rd1 ** 2)) * g_rd2 * (point1 - expected_point1)
			rate2 += (Q * (rd2 ** 2)) * g_rd1 * (point2 - expected_point2)
			
			# 計算後レート情報保存
			account_type1_rate[t.player1_account_id][t.player1_type1_id][:rate] = rate1
			account_type1_rate[t.player1_account_id][t.player1_type1_id][:rd] = rd1
			account_type1_rate[t.player1_account_id][t.player1_type1_id][:last_timestamp] = t.rep_timestamp
			account_type1_rate[t.player2_account_id][t.player2_type1_id][:rate] = rate2
			account_type1_rate[t.player2_account_id][t.player2_type1_id][:rd] = rd2
			account_type1_rate[t.player2_account_id][t.player2_type1_id][:last_timestamp] = t.rep_timestamp
			
			# 対戦アカウント保存
			account_type1_rate[t.player1_account_id][t.player1_type1_id][:account_ids] << t.player2_account_id
			account_type1_rate[t.player2_account_id][t.player2_type1_id][:account_ids] << t.player1_account_id

			# 対戦数保存
			account_type1_rate[t.player1_account_id][t.player1_type1_id][:counts] += 1
			account_type1_rate[t.player2_account_id][t.player2_type1_id][:counts] += 1
			
		end
		
		res_body << "ratings calculated...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# 現在のRDを算出
		account_type1_rate.each do |account_id, type1_rate|
			type1_rate.each do |type1_id, rate_info|
				rate_info[:rd] = [(rate_info[:rd] ** 2.0 + RD_DEC * (now - rate_info[:last_timestamp])) ** 0.5, MAX_RD].min
			end
		end
		
		res_body << "RD calculated...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# レート平均を INIT_RATE に合わせる
		sum = 0
		num = 0
		account_type1_rate.each do |account_id, type1_rate|
			type1_rate.each do |type1_id, rate_info|
				sum += rate_info[:rate]
				num += 1
			end
		end
		
		res_body << "ratings avarage calculated...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		avg = sum.to_f / num.to_f
		account_type1_rate.each do |account_id, type1_rate|
			type1_rate.each do |type1_id, rate_info|
				rate_info[:rate] += (INIT_RATE - avg)
			end
		end
		
		res_body << "レート平均を #{avg} から #{INIT_RATE} に調整しました。\n"
		sum = num = avg = nil
		
		res_body << "ratings avarage adjusted...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# 計算結果をDBに保存
		begin
			require 'GameAccountRating'
			
			account_type1_rate.each do |account_id, type1_rate|
				type1_rate.each do |type1_id, rate_info|
				
					# 更新または作成
					res_update = db.exec(<<-"SQL")
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
			end
				
		rescue => ex
			res_status = "Status: 500 Server Error\n"
			res_body << "レーティング計算時にエラーが発生しました。\n"
			raise ex
		else
			res_body << "レーティング計算を正常に実行しました。\n"
		end
		
		res_body << "rating results stored...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
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
