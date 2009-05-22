class GameAccountRating
	attr_accessor :id, :game_id, :account_id, :type1_id, :type2_id, :rating, :ratings_deviation, :elo_rating_value, :matched_accounts, :match_counts, :created_at, :updated_at, :lock_version, :game_type1_ratings_rank, :game_each_type1_ratings_rank
	
	# 汎用アカウント表示用
	attr_accessor :account_name, :rep_name, :game_pov_class_id, :show_ratings_flag, :cluster_id, :cluster_name
	
end
