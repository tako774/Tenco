class Replay
  attr_accessor :id, :created_at, :updated_at
  attr_accessor :game_id, :track_record_id, :relative_file_path, :player1_account_id, :player1_type1_id
  
  attr_accessor :play_timestamp
  attr_accessor :player1_rating, :player1_ratings_deviation, :player1_matched_accounts
  attr_accessor :player2_type1_id
  attr_accessor :player2_rating, :player2_ratings_deviation, :player2_matched_accounts
end
