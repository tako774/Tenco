require 'DaoBase'
require 'Game'

class GameDao < DaoBase
	
	# バッチ処理対象のゲームIDを取得
	def get_batch_target_ids
		ids = []
		
		res = @db.exec(<<-"SQL")
			SELECT
			  id
			FROM
			  games
			WHERE
			  is_batch_target = 1
		SQL

		res.each do |r|
			ids << r[0].to_i
		end
		res.clear	
		
		return ids
	end
	
	# レート計算対象のゲームIDを取得
	def get_rating_targets
		games = []
		
		res = @db.exec(<<-"SQL")
			SELECT
			  id, match_end_at
			FROM
			  games
			WHERE
			  is_batch_target = 1
		SQL

		res.each do |r|
			g = Game.new
			res.num_fields.times do |i|
				g.instance_variable_set("@#{res.fields[i]}", r[i])
			end
			games << g
		end
		res.clear	
		
		return games
	end
end
