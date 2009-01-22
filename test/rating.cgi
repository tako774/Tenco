#!/usr/bin/ruby

# 開始時刻
now = Time.now

### レーティング計算 API ###
REVISION = '0.05'
DEBUG = 1

$LOAD_PATH.unshift '../common'
$LOAD_PATH.unshift '../model'

require 'rubygems'
require 'active_record'
require 'kconv'
require 'yaml'
require 'time'

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
		INIT_RATE = 1500.0
		K_FACTOR = 16 # K-factor
		
		account_type1_rate = {}     # アカウント・キャラごとのレート
		account_type1_account_ids = {} # アカウント・キャラごとの対戦アカウント
		account_type1_count = {}   # アカウント・キャラごとの対戦数
		
		# DB設定ファイル読み込み
		config_file = '../../../config/database.yaml'
		config = YAML.load_file(config_file)

		# DB接続
		ActiveRecord::Base.establish_connection(
		  :adapter  => config['adapter'],
		  :host     => config['host'],
		  :username => config['username'],
		  :password => config['password'],
		  :database => config['database']
		)
		
		res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# レート係数取得			
		# require 'EloRatingFactor'
		# rating_factors = EloRatingFactor.find(:all, :conditions => ["game_id = :game_id", :game_id => game_id])
		
		# アカウントの対戦記録を取得
		# 発生時間順でソート
		# 自分と相手の認識時間の中間を発生時間とする
		require 'TrackRecord'
		track_records = TrackRecord.find_by_sql([<<-SQL, {:game_id => game_id.to_i}])
			SELECT
			  *, t2.play_timestamp AS player2_timestamp
			FROM
			  track_records t1,
			  track_records t2				
			WHERE
			  t1.matched_track_record_id = t2.id
			  AND t1.id > t1.matched_track_record_id
			  AND t1.game_id = :game_id
			ORDER BY
			  t1.play_timestamp + (t2.play_timestamp - t1.play_timestamp) /2
			SQL
		
		res_body << "#{track_records.length} 件の対戦結果をレート計算対象として取得。\n"
		res_body << "matched trackrecords selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# 発生時間順にレート計算
		track_records.each do |t|
		
			# アカウント・タイプ別レート情報初期化
			account_type1_rate[t.player1_account_id] ||= {}
			account_type1_rate[t.player2_account_id] ||= {}
			account_type1_rate[t.player1_account_id][t.player1_type1_id] ||= {:rate => INIT_RATE, :account_ids => [], :counts => 0}
			account_type1_rate[t.player2_account_id][t.player2_type1_id] ||= {:rate => INIT_RATE, :account_ids => [], :counts => 0}
			# 対戦前レート情報取得
			rate1 = account_type1_rate[t.player1_account_id][t.player1_type1_id][:rate]
			rate2 = account_type1_rate[t.player2_account_id][t.player2_type1_id][:rate]
			point1 = (1 + (t.player1_points <=> t.player2_points)) / 2
			point2 = (1 + (t.player2_points <=> t.player1_points)) / 2
						
			# レート計算
			expected_point1 = 1.to_f / (1 + 10 ** ((rate2 - rate1) / 400))
			expected_point2 = 1.to_f - expected_point1
			
			rate1 += K_FACTOR.to_f * (point1 - expected_point1)
			rate2 += K_FACTOR.to_f * (point2 - expected_point2)
			
			# 計算後レート保存
			account_type1_rate[t.player1_account_id][t.player1_type1_id][:rate] = rate1
			account_type1_rate[t.player2_account_id][t.player2_type1_id][:rate] = rate2
			
			# 対戦アカウント保存
			account_type1_rate[t.player1_account_id][t.player1_type1_id][:account_ids] << t.player2_account_id
			account_type1_rate[t.player2_account_id][t.player2_type1_id][:account_ids] << t.player1_account_id

			# 対戦数保存
			account_type1_rate[t.player1_account_id][t.player1_type1_id][:counts] += 1
			account_type1_rate[t.player2_account_id][t.player2_type1_id][:counts] += 1
			
		end
		
		res_body << "ratings calculated...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# 計算結果をDBに保存
		begin
			require 'GameAccountRating'
			GameAccountRating.transaction do
				account_type1_rate.each do |account_id, type1_rate|
					type1_rate.each do |type1_id, rate_info|
						# 更新対象レコード取得、なければ生成
						game_account_rating = GameAccountRating.find(
							:first,
							:conditions => [
								"game_id = :game_id AND account_id = :account_id AND type1_id = :type1_id",
								{:game_id => game_id, :account_id => account_id, :type1_id => type1_id}
							]
						) 
						
						unless game_account_rating then
							game_account_rating = GameAccountRating.new
							game_account_rating.game_id    = game_id
							game_account_rating.account_id = account_id
							game_account_rating.type1_id   = type1_id
						end  
						
						game_account_rating.elo_rating_value = rate_info[:rate]
						game_account_rating.matched_accounts = rate_info[:account_ids].uniq.length
						game_account_rating.match_counts = rate_info[:counts]
						game_account_rating.save!
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
		ActiveRecord::Base.remove_connection if ActiveRecord::Base.connected?
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
