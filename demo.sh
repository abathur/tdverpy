export PAGER="$(type -p cat)"

phase()(
	printf "\n>>> $1\n"
	echo "-------------------------------------------------"
	shift
	set -x
	$@
)

create_playground(){
	playground="$(mktemp -d)"
	pushd "$playground"
	git config user.email "testyboi@example.com"
	git config user.name "Testy Boi"
}

init_git_repo(){
	git init -b main
	git log --patch
}

status_check(){
	git log --patch
	git status
	git diff
}

tdver_post_init_options(){
	tdver --help
	tdver check
	tdver support
	tdver release
}

add_testy_tests(){
	mkdir tests bugs
	echo true > tests/test1
	tdver check
	git add tests bugs
	tdver check
	git commit -m "add some testy-tests"
	tdver check
	tdver release
}

add_regression_tests(){
	echo true > bugs/test1
	git add bugs
	git commit -m "add some regressy-tests"
	tdver check
}

add_mixed_tests(){
	echo true > tests/test2
	git add tests
	git commit --amend --no-edit
	tdver check
}
remove_a_test(){
	git rm tests/test1
	git commit --amend --no-edit
	tdver check
}

echo "painfully-terse tdver demo :)"
echo "================================================="
echo "first I will make a playground, cd to it, & set a committer identity"
echo "-------------------------------------------------"
create_playground
phase "then init a git repo" init_git_repo
phase "now to look at tdver" "tdver --help"
phase "before we begin using tdver, our only option is to start" "tdver start"
phase "what did that do?" status_check
phase "now I have more options" tdver_post_init_options
phase "what did that do?" status_check
phase "ok, now add some tests" add_testy_tests
phase "what did that do?" status_check
phase "ok, now add some regression tests" add_regression_tests
phase "what did that do?" status_check
phase "what if we add a mix?" add_mixed_tests
phase "what if we remove one?" remove_a_test
phase "where did we end up?" status_check
