require 'DaoBase'
require 'ProfileProperty'

class ProfilePropertyDao < DaoBase
	@@version = 0.02
  
	# 指定されたIDのプロファイルプロパティ情報を返す
	def get_by_id(id)
		profile_property = nil
		
		res = @db.exec(<<-"SQL")
			SELECT
			  pp.*
			FROM
			  profile_properties pp
			WHERE
			  pp.id = #{id.to_i}
		SQL

		if res.num_tuples == 1 then
			profile_property = ProfileProperty.new
			res.num_fields.times do |i|
				profile_property.instance_variable_set("@#{res.fields[i]}", res[0][i])
			end
		end
		
		res.clear
			
		return profile_property
	end
	
	# 指定されたプロパティ名のプロファイルプロパティ情報を返す
	def get_by_name(property_name)
		profile_property = nil
		
		res = @db.exec(<<-"SQL")
			SELECT
			  pp.*
			FROM
			  profile_properties pp
			WHERE
			  pp.name = #{s property_name}
		SQL

		if res.num_tuples == 1 then
			profile_property = ProfileProperty.new
			res.num_fields.times do |i|
				profile_property.instance_variable_set("@#{res.fields[i]}", res[0][i])
			end
		end
		
		res.clear
			
		return profile_property
	end
	
	# プロファイルプロパティをすべて返す
	def get_all
		profile_properties = []
		
		res = @db.exec(<<-"SQL")
			SELECT
			  pp.*,
			  pc.name AS class_name,
			  pc.display_name AS class_display_name
			FROM
			  profile_properties pp,
			  profile_classes pc
			WHERE
			  pp.profile_class_id = pc.id
		SQL

		res.each do |row|
			pp = ProfileProperty.new
			res.num_fields.times do |i|
				pp.instance_variable_set("@#{res.fields[i]}", row[i])
			end
			profile_properties << pp
		end
		
		res.clear
			
		return profile_properties
	end
end
