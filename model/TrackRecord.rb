class TrackRecord < ActiveRecord::Base
	validates_presence_of :game_id, :player1_account_id, :player1_points, :player1_type1_id, :player2_type1_id, :player2_points
	
	validates_uniqueness_of :id
	
	validates_numericality_of :game_id, :only_integer => true
	validates_numericality_of :player1_account_id, :only_integer => true
	validates_numericality_of :player1_type1_id, :only_integer => true
	validates_numericality_of :player2_type1_id, :only_integer => true
	
	validates_length_of :player1_name, :minimum => 1
	validates_length_of :player2_name, :minimum => 1
end
