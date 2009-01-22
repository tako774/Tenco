### エンティティの基底クラス ###
# 配列名でインスタンス変数にアクセス可能にする

class Entity
	def [](field)
		field_class = field.class.to_s
		eval("self.#{field}") if (field_class == "String" and field =~ /[a-zA-Z_][a-zA-Z0-9_]*/) or field_class == "Symbol"
	end
	
	def []=(field, value)
		field_class = field.class.to_s
		eval("self.#{field} = value") if (field_class == "String" and field =~ /[a-zA-Z_][a-zA-Z0-9_]*/) or field_class == "Symbol"
	end
end
