require "#{File.expand_path(File.dirname(__FILE__))}/DaoBase"
require "#{File.expand_path(File.dirname(__FILE__))}/../entity/GameType1"

class GameType1Dao < DaoBase
	@@version = 0.00
	
	# 指定されたゲームIDたちの情報をすべてかえす
	def get_by_game_ids(game_ids)
		game_type1s = {} # game_id => { type1_id => game_type1 }
    return game_type1s if game_ids.length == 0
		
		res = @db.exec(<<-"SQL")
			SELECT
        gt.*
			FROM
        game_type1s gt
			WHERE
			  gt.game_id IN (#{(game_ids.map { |i| "'#{i.to_i}'" } ).join(", ")})
		SQL

		res.each do |row|
			gt = GameType1.new
			res.num_fields.times do |i|
				gt.instance_variable_set("@#{res.fields[i]}", row[i])
			end
			game_type1s[gt.game_id.to_i] ||= {}
      game_type1s[gt.game_id.to_i][gt.type1_id.to_i] = gt
		end
		
		res.clear
			
		return game_type1s
	end
end
