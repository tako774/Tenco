require 'DaoBase'
require 'Game'
require 'time'

class GameDao < DaoBase
	
	# ゲーム情報を取得
	# 引数でゲームIDを条件として指定可能（配列もしくは数値・文字列）
	# 引数指定がなければ全ゲームを取得
	def get_games(*ids)
		ids.flatten!
		games = {}
		
		res = @db.exec(<<-"SQL")
			SELECT
			  *
			FROM
			  games
			#{"--" if ids.length == 0} WHERE id IN (#{(ids.map{ |i| i.to_i }).join(",")})
		SQL
		
		res.each do |r|
			g = Game.new
			res.fields.length.times do |i|
				g.instance_variable_set("@#{res.fields[i]}", r[i])
			end
      g.match_start_at = Time.parse(g.match_start_at) if g.match_start_at
      g.match_end_at = Time.parse(g.match_end_at) if g.match_end_at
			games[g.id.to_i] = g
		end
		
		return games
	end
	
	# ゲームIDを引数として、ゲーム情報を取得
	def get_game_by_id(game_id)
		game = nil
		
		res = @db.exec(<<-"SQL")
			SELECT
				*
			FROM
				games
			WHERE
				id = #{game_id.to_i}
		SQL
		
		if res.num_tuples == 1 then
			game = Game.new
			res.num_fields.times do |i|
				game.instance_variable_set("@#{res.fields[i]}", res[0][i])
			end
      game.match_start_at = Time.parse(game.match_start_at) if game.match_start_at
      game.match_end_at = Time.parse(game.match_end_at) if game.match_end_at
			res.clear
		end
		
		return game
	end
  
	# バッチ処理対象のゲーム情報を取得
	def get_batch_target_games
		games = {}
		
		res = @db.exec(<<-"SQL")
			SELECT
			  *
			FROM
			  games
			WHERE
			  id IN (#{(id.map{ |i| i.to_i }).join(",")})
		SQL
		
		res.each do |r|
			g = Game.new
			res.fields.length.times do |i|
				g.instance_variable_set("@#{res.fields[i]}", r[i])
			end
      g.match_start_at = Time.parse(g.match_start_at) if g.match_start_at
      g.match_end_at = Time.parse(g.match_end_at) if g.match_end_at
			games[g.id.to_i] = g
		end
		
		return games
	end
	
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
