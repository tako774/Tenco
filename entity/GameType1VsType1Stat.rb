class GameType1VsType1Stat
	attr_accessor :id, :game_id, :type1_id, :matched_type1_id, :date_time, :track_records_count, :wins, :loses, :created_at, :updated_at, :lock_version
	
	# キャラ対キャラ別統計用
	attr_accessor :ideal_rating_diff
end
