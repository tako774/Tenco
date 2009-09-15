require 'db'

class GameProfileUtil
	VERSION = 'v0.01'

	# ゲーム内プロファイルごとのレート推定算出
	# <引数>
	# names    : （必須）ゲーム内プロファイル名（配列可）（複数要素の場合、複数プロファイル名を使う同一プレイヤーとみなす）
	# game_id  : （必須）対象ゲームID
	# type1_ids : （任意）対象キャラID（配列可）、未指定の場合は全キャラクターについて推定
	# <戻り値>
	# { type1_id => {:track_record_counts => track_record_counts, :log_likelihood => { rating => log_likelihood }] }
	def self.estimate_rating (names, game_id, type1_ids = nil)
		# 戻り値
		estimations = {} 
		
		# レート候補
		rates = [900.0, 950.0, 1000.0, 1050.0, 1100.0, 1150.0, 1200.0, 1250.0, 1300.0, 1350.0, 1400.0, 1450.0, 1500.0, 1550.0, 1600.0, 1650.0, 1700.0, 1750.0, 1800.0, 1850.0, 1900.0, 1950.0, 2000.0, 2050.0, 2100.0, 2150.0, 2200.0, 2250.0, 2300.0, 2350.0, 2400.0]
		# 対戦結果
		track_records = []
	
		if names.class != Array then
			names = [names.to_s]
		end
		
		if !type1_ids.nil? && type1_ids.class != Array then
			type_ids = [type1_ids.to_i]
		end
		
		# DB接続取得
		db = DB.getInstance()
				
		# 対戦結果データ取得
		require 'Game'
		res_game = db.exec(<<-"SQL")
			SELECT
			  name
			FROM
			  games
			WHERE
			  id = #{game_id.to_i}
		SQL
		
		if res_game.num_tuples >= 1 then
			game_name = res_game[0][0]
			type1_ids_str = ""
			type1_ids_str = (type1_ids.map { |id| id.to_i }).join(", ") unless type1_ids.nil?
		
			require 'TrackRecordRate'
			res = db.exec(<<-"SQL")
				SELECT
				  t.player1_points,
				  t.player2_points,
				  t.player2_type1_id,
				  gar.rating,
				  gar.ratings_deviation
				FROM
				  game_account_ratings gar,
				  track_records t
				WHERE
				  t.game_id = #{game_id.to_i}
				  AND gar.game_id = #{game_id.to_i}
				  AND t.player2_name in (#{(names.map { |n| s n }).join(", ")})
				  #{"AND t.player2_type1_id in (" + type1_ids_str + ")" unless type1_ids_str.empty? }
				  AND t.player1_account_id = gar.account_id
				  AND t.player1_type1_id = gar.type1_id
				  AND gar.ratings_deviation < 100
				SQL
				
			res.each do |r|
				t = TrackRecordRate.new
				# 高速化のためインスタンス名直接指定
				t.player1_points = r[0].to_i
				t.player2_points = r[1].to_i
				t.player2_type1_id = r[2].to_i
				t.rating = r[3].to_f
				t.ratings_deviation = r[4].to_f
#			res.num_fields.times do |i|
#				t.instance_variable_set("@#{res.fields[i]}", r[i])
#			end
				track_records << t
			end
			res.clear
					
			
			# 対戦結果が取得できたときはレート推定
			if track_records.length > 0 then
							
				# 発生時間順にレート計算
				track_records.each do |t|
					type1_id = t.player2_type1_id.to_i
					
					# 推定情報初期化
					unless estimations[type1_id]
						estimations[type1_id] ||= {
							:track_record_counts => 0,
							:log_likelihood => {},
						}
						rates.each do |rate|
							estimations[type1_id][:log_likelihood][rate] = 0.0
						end
					end
					
					# 対戦数カウント
					estimations[type1_id][:track_record_counts] += 1
					
					# Player2 取得ポイント
					point = (1.0 + (t.player2_points.to_i <=> t.player1_points.to_i)) * 0.5
					
					# レートごとの尤度計算
					rates.each do |rate|
						# 期待勝率
						p_win = 1.0 / (1.0 + 10.0 ** ((t.rating - rate) / 400.0))
						# 発生尤度加算
						if point == 1
							estimations[type1_id][:log_likelihood][rate] += Math.log(p_win)
						elsif point == 0
							estimations[type1_id][:log_likelihood][rate] += Math.log(1 - p_win)
						end
					end
					
				end
				
				# 尤度のもっとも高いレートを記録
				estimations.each do |type1_id, est|
					type1_log_likelihood = est[:log_likelihood]
					array = type1_log_likelihood.to_a.sort do |a, b|
						b[1] <=> a[1]
					end
					if array[0][1] <= -10
						est[:rating] = array[0][0]
					else
						est[:rating] = nil
					end
				end
				
			end	
		end
		
		return estimations
	end
end
