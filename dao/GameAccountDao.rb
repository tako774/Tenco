require 'DaoBase'

class GameAccountDao < DaoBase
	
	# 指定されたゲームID・アカウントIDの、マッチ済みアカウントIDリストを返す
	# 最終対戦時刻の降順で返す
	def get_matched_account_ids(game_id, account_id)
		matched_account_ids = []
		
		res = @db.exec(<<-"SQL")
			SELECT
			  gava.matched_account_id
			FROM
			  game_account_vs_accounts gava,
			  accounts a
			WHERE
			  gava.game_id = #{game_id.to_i}
			  AND gava.account_id = #{account_id.to_i}
			  AND gava.matched_account_id = a.id
			  AND a.del_flag = 0
			ORDER BY
			  last_play_timestamp DESC
		SQL

		res.each do |r|
			matched_account_ids << r[0].to_i
		end
		res.clear	
		
		return matched_account_ids
	end
	
end
