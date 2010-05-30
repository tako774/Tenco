require 'pg'

class PGresult
	alias :cmdstatus :cmd_status
	
	alias :row_hash :[]
	
	def [](row_no)
		self.num_fields.times.map { |field_no| self.getvalue(row_no, field_no) }
	end
	
	alias :each_as_hash :each
	
	def each
		self.num_tuples.times.map do |row_no|
			yield(self[row_no])
		end
	end
end
