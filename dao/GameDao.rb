require 'DaoBase'
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
end
