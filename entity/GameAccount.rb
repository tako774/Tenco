class GameAccount
	attr_accessor :id, :account_id, :game_id, :created_at, :updated_at, :lock_version, :rep_name
	
	# game_account.cgi 用
	attr_accessor :account_name
	
	# account.cgi 用
	attr_accessor :game_name
end

	
