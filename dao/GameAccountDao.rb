require 'DaoBase'
require 'GameAccount'
require 'GameAccountVsAccount'

class GameAccountDao < DaoBase
	@@version = 0.01
	
	# 指定されたゲームID・アカウントIDの、マッチ済みアカウントIDリストを返す
	# 最終対戦時刻の降順で返す
	def get_matched_accounts(game_id, account_id)
		matched_accounts = []
		
		res = @db.exec(<<-"SQL")
			SELECT
			  gava.matched_account_id,
			  gava.wins,
			  gava.loses
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
      ac = GameAccountVsAccount.new
      ac.matched_account_id = r[0].to_i
      ac.wins  = r[1].to_i
      ac.loses = r[2].to_i
			matched_accounts << ac
		end
		res.clear
		
		return matched_accounts
	end
	
	def key_to_account_id(key)
		if key =~ /_(.+)$/ then
			return $1.to_i(36).to_s
		else
			return nil
		end
	end
	
	def id_to_key(game_id, account_id)
		"ga#{game_id.to_i.to_s(36)}_#{account_id.to_i.to_s(36)}"
	end
	
	def delete_by_ids(game_id, account_ids)
		account_ids.each do |account_id|
			begin
				@cache.delete id_to_key(game_id, account_id)
			rescue Memcached::NotFound
			end
		end
	end
	
	# 指定されたゲームID・アカウントIDリストの情報を返す
	def get_game_accounts(game_id, account_ids)
		game_account_hash = {}
		game_accounts = []
		
		game_id = game_id.to_s
		account_ids = account_ids.map { |id| id.to_s }
		
		if account_ids.length > 0 then
			
			cache_keys = account_ids.map { |account_id| id_to_key(game_id, account_id) }
			@cache.get(cache_keys, true).each do |key, data|
				game_account_hash[key_to_account_id(key).to_s] = data
			end
			missed_account_ids = account_ids - game_account_hash.keys
			
			if missed_account_ids.length > 0 then
				res = @db.exec(<<-"SQL")
					SELECT
					  ga.account_id,
					  a.name,
					  ga.rep_name
					FROM
					  game_accounts ga,
					  accounts a
					WHERE
					  ga.game_id = #{game_id.to_i}
					  AND ga.account_id IN (#{(missed_account_ids.map { |i| "'#{i.to_i}'" } ).join(", ")})
					  AND a.id = ga.account_id
				SQL
				
				res.each do |r|
					# 数字の文字列は、整数に変換
					ga = GameAccount.new
					ga.game_id = game_id.to_i
					ga.account_id = r[0].to_i
					ga.account_name = r[1]
					ga.rep_name = r[2] || r[1]
					game_account_hash[ga.account_id.to_s] = ga
					
					begin
						@cache.add(id_to_key(ga.game_id, ga.account_id), ga, true)
					rescue Memcached::NotStored
					end
				end
			end
		
			account_ids.each do |account_id|
				game_accounts << game_account_hash[account_id.to_s]
			end
			game_accounts.compact!
			
		end
				
		return game_accounts
	end
end
