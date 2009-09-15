# DAOの基底クラス
class DaoBase

	protected
	def initialize()
		$LOAD_PATH.unshift '../entity'
		$LOAD_PATH.unshift '../common'
		require 'db'
		
		@db = DB.getInstance()
	end

end
