class TrackRecord
	attr_accessor :id, :game_id, :play_timestamp, :player1_account_id, :player1_name, :player1_type1_id, :player1_type2_id, :player1_points, :player2_account_id, :player2_name, :player2_type1_id, :player2_type2_id, :player2_points, :created_at, :updated_at, :lock_version, :matched_track_record_id, :rep_timestamp
	
	# game_account.cgi —p
	attr_accessor :player2_account_name, :player2_rep_name, :player2_account_del_flag
end
