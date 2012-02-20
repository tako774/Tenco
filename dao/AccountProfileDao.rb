require "#{File.expand_path(File.dirname(__FILE__))}/DaoBase"
require "#{File.expand_path(File.dirname(__FILE__))}/../entity/AccountProfile"

class AccountProfileDao < DaoBase
	@@version = 0.02
	TWITTER_PROPERTY_NAME = "twitter"
	
	# 指定されたアカウントID,プロパティ名のアカウントプロパティを登録する
	def add(account_id, property_id, value, visibility, uri = nil)
		
		res = @db.exec(<<-"SQL")
			INSERT INTO
			  account_profiles (
			    account_id
			  , profile_property_id
			  , is_visible
			  , value
			  #{", uri" if uri}
			  )
			VALUES (
			    #{account_id.to_i}
			  , #{property_id.to_i}
			  , #{visibility.to_i}
			  , #{s value}
			  #{", #{s(uri)}" if uri}
			)
			RETURNING id
		SQL
		
		return res[0][0]
	end
	
	def get_account_profiles_by_property_id(account_id, property_id)
		account_profiles = []
		
		res = @db.exec(<<-"SQL")
			SELECT
			  ap.*
			FROM
			  account_profiles ap
			WHERE
			  account_id = #{account_id.to_i}
			  AND profile_property_id = #{property_id.to_i}
			ORDER BY
			  ap.id
		SQL
		
		res.each do |row|
			ap = AccountProfile.new
			res.num_fields.times do |i|
				ap.instance_variable_set("@#{res.fields[i]}", row[i])
			end
			account_profiles << ap
		end
		
		res.clear
		
		return account_profiles
	end
	
	def get_by_account_id(account_id, options = {})
		account_profiles = []
		
		res = @db.exec(<<-"SQL")
			SELECT
			  ap.*,
			  pp.is_unique,
			  pp.name,
			  pp.display_name,
			  pc.name AS class_name,
			  pc.display_name AS class_display_name
			FROM
			  account_profiles ap,
			  profile_properties pp,
			  profile_classes pc
			WHERE
			  ap.account_id = #{account_id.to_i}
			  AND ap.profile_property_id = pp.id
			  AND pp.profile_class_id = pc.id
			  #{"AND ap.is_visible = 1" if options[:visibility_check] }
			ORDER BY
			  pc.id,
			  ap.id
		SQL
		
		res.each do |row|
			ap = AccountProfile.new
			res.num_fields.times do |i|
				ap.instance_variable_set("@#{res.fields[i]}", row[i])
			end
			account_profiles << ap
		end
		
		res.clear
		
		return account_profiles
	end
	
	def get_by_account_name(account_name, options = {})
		account_profiles = []
		options ||= {}
		
		res = @db.exec(<<-"SQL")
			SELECT
			  ap.*,
			  pp.is_unique,
			  pp.name,
			  pp.display_name,
			  pc.name AS class_name,
			  pc.display_name AS class_display_name,
			  pc.id AS class_id
			FROM
			  account_profiles ap,
			  profile_properties pp,
			  accounts a,
			  profile_classes pc
			WHERE
			  a.name = #{s account_name}
			  AND ap.account_id = a.id
			  AND ap.profile_property_id = pp.id
			  AND pp.profile_class_id = pc.id
			  #{"AND ap.is_visible = 1" if options[:visibility_check] }
			ORDER BY
			  pc.id,
			  ap.id
		SQL
		
		res.each do |row|
			ap = AccountProfile.new
			res.num_fields.times do |i|
				ap.instance_variable_set("@#{res.fields[i]}", row[i])
			end
			account_profiles << ap
		end
		
		res.clear
		
		return account_profiles
	end
	
	def delete_by_id(id)
		res = @db.exec(<<-"SQL")
			DELETE FROM
			  account_profiles ap
			WHERE
			  ap.id = #{id.to_i}
		SQL
	end
	
	def get_twitter_data_by_account_ids(account_ids, options = {:visibility_check => true} )
		
		account_twitter_uris = {}
		
		res = @db.exec(<<-"SQL")
			SELECT
			    account_id,
			    uri
			FROM
			  account_profiles ap
			WHERE
			  ap.profile_property_id = (
			    SELECT
			      id
			    FROM
			      profile_properties
			    WHERE
			      name = #{s TWITTER_PROPERTY_NAME}
			  )
			  AND ap.account_id IN (#{(account_ids.map { |i| "'#{i.to_i}'" } ).join(", ")})
			  #{"AND ap.is_visible = 1" if options[:visibility_check] }
		SQL
		
		res.each do |row|
			account_id = row[0].to_i
			uri = row[1]
			
			if screen_name = twitter_screen_name_from_uri(uri) then
				account_twitter_uris[account_id] ||= []
				account_twitter_uris[account_id] << { :uri => uri, :screen_name => screen_name }
			end
		end
		
		res.clear
		
		return account_twitter_uris
	end
end
