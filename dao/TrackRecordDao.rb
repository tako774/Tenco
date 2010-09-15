require 'DaoBase'
require 'base64'
require 'TrackRecord'

class TrackRecordDao < DaoBase
	@@version = 0.04
	# 指定されたゲームID・アカウントIDの対戦結果レコードIDリストを取得
	# 結果のIDの降順でソートされる
	def get_ids_by_game_account(game_id, account_id)
		ids = []
		game_id = game_id.to_i
		account_id = account_id.to_i
		
		key = "tr#{game_id.to_i.to_s(36)}_#{account_id.to_i.to_s(36)}"
		
		begin 
			value = @cache.get(key)
			ids = value.unpack('I*').sort! { |a,b| b <=> a }
		rescue Memcached::NotFound
			res = @db.exec(<<-"SQL")
				SELECT
				  id
				FROM
				  track_records
				WHERE
				  game_id = #{game_id.to_i}
				  AND player1_account_id = #{account_id.to_i}
				ORDER BY
				  id DESC
			SQL

			res.each do |r|
				ids << r[0].to_i
			end
			res.clear
			
			begin
				@cache.add(key, ids.pack('I*'))
			rescue Memcached::NotStored
			end
		end
		
		return ids
	end

	# 対戦結果idのリストから、対戦結果データを取得
	def get_track_records_by_ids(ids)
		track_records = []
		track_record_hash = {} # key => データ形式の対戦結果データ
		missed_ids = []
		
		ids = ids.map! { |i| i.to_s }
		
		cache_keys = ids.map { |i| id_to_key(i) }
		@cache.get(cache_keys, true).each do |key, data|
			track_record_hash[key_to_id(key).to_s] = data
		end
		missed_ids = ids - track_record_hash.keys
		
		if missed_ids.length > 0 then
		
			res = @db.exec(<<-"SQL")
				SELECT
					t.id,
					EXTRACT(EPOCH FROM t.play_timestamp) AS play_timestamp,
					t.player1_name,
					t.player1_type1_id,
					t.player1_points,
					CASE
						WHEN a2.name IS NULL
						THEN t.encrypted_base64_player2_name
						ELSE t.player2_name
					END AS player2_name,
					t.player2_type1_id,
					t.player2_points,
					a2.id AS player2_account_id,
					a2.name AS player2_account_name,
					a2.del_flag AS player2_account_del_flag
				FROM
					track_records t
					LEFT OUTER JOIN
					  accounts a2
					ON
					  t.player2_account_id = a2.id
					  AND a2.del_flag = 0
				WHERE
					t.id in (#{(missed_ids.map { |i| "'#{i.to_i}'" }).join(", ")})
			SQL
			
			res.each do |r|
				track_record_id = r.shift
				
				# 数字の文字列は、整数に変換
				r[0] = r[0].to_i if r[0]
				r[2] = r[2].to_i if r[2]
				r[3] = r[3].to_i if r[3]
				r[5] = r[5].to_i if r[5]
				r[6] = r[6].to_i if r[6]
				r[7] = r[7].to_i if r[7]
				r[9] = r[9].to_i if r[9]
				track_record_hash[track_record_id] = r
				
				begin
					@cache.add(id_to_key(track_record_id), r, true)
				rescue Memcached::NotStored
				end
			end
			
			res.clear
			
		end # if missed_ids.length > 0
		
		track_record_hash.each do |track_record_id, r|
			t = TrackRecord.new
			
			t.id = track_record_id
			t.play_timestamp = Time.at(r[0])
			t.player1_name = r[1]
			t.player1_type1_id = r[2]
			t.player1_points = r[3]
			t.player2_name = r[4]
			t.player2_type1_id = r[5]
			t.player2_points = r[6]
			t.player2_account_id = r[7]
			t.player2_account_name = r[8]
			t.player2_account_del_flag = r[9]
			
			track_records << t
		end
		
		return track_records
	end
	
	def id_to_key(track_record_id)
		"tid#{track_record_id.to_i.to_s(36)}"
	end
	
	def key_to_id(key)
		key.sub(/tid/, '').to_i(36).to_s
	end
	
	def delete_by_ids(ids)
		ids.each do |track_record_id|
			begin
				@cache.delete id_to_key(track_record_id)
			rescue Memcached::NotFound
			end
		end
	end
	
=begin
	# 指定された game_id,player2_name,player2_type1_id の対戦結果idリストを取得します
	def get_ids_by_game_p2name_p2type1(game_id, player2_name, player2_type1_id)
		ids = []
		game_id = game_id.to_i
		player2_name = player2_name
		player2_type1_id = player2_type1_id.to_i
		
		key = ["trgnt", game_id.to_s(36), Base64.encode64(player2_name).gsub(/[=\n]/, ''), player2_type1_id.to_s(36)].join("_")
		
		begin
			ids = (@cache.get(key)).unpack('I*')
		rescue Memcached::NotFound
			res = @db.exec(<<-"SQL")
				SELECT
				  id
				FROM
				  track_records
				WHERE
				  game_id = #{game_id.to_i}
				  AND player2_name = #{s player2_name}
				  AND player2_type1_id = #{player2_type1_id.to_i}
			SQL

			res.each do |r|
				ids << r[0].to_i
			end
			res.clear
			
			begin
				@cache.add(key, ids.pack('I*'))
			rescue Memcached::NotStored 
			end
		end
		
		return ids
	end
=end
	
end
