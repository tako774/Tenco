require 'DaoBase'
#require 'TrackRecord'

class TrackRecordDao < DaoBase
	
	# 指定されたゲームID・アカウントIDの対戦結果レコードIDリストを取得
	# 結果のIDの降順でソートされる
	def get_track_record_ids(game_id, account_id)
		ids = []
		game_id = game_id.to_i
		account_id = account_id.to_i
		
		begin 
			value = @cache.get("tr#{game_id.to_i.to_s(36)}_#{account_id.to_i.to_s(36)}")
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
		end
		
		return ids
	end
	
end
