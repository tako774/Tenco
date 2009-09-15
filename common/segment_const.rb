# 区分値ファイル
# 2009/08/08 21:08:15 生成

SEG = {
	# POV評価単位(2)
	:pov_eval_unit => {
		:id => 2,
		:name => 'POV評価単位'
	},	# 仮想タイプ１(3)
	:virtual_type1 => {
		:id => 3,
		:name => '仮想タイプ１'
	}
}

SEG_V = {
	# POV評価単位(2)
	:pov_eval_unit => {
		:system => {
			:value => 0,
			:name => 'Tenco! 全体'
		},
		:game => {
			:value => 1,
			:name => 'ゲーム別'
		},
		:game_type1 => {
			:value => 2,
			:name => 'キャラクター別'
		}
	},	# 仮想タイプ１(3)
	:virtual_type1 => {
		:random => {
			:value => 99999998,
			:name => 'ランダム'
		},
		:all => {
			:value => 99999999,
			:name => 'キャラ全体'
		}
	}
}

