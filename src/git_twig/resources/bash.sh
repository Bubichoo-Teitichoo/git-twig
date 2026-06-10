_git_twig_completion() {
    local IFS=$'\n'
    local response

    response=$(env COMP_WORDS="${COMP_WORDS[*]}" COMP_CWORD=$((COMP_CWORD)) _GIT_TWIG_COMPLETE="bash_complete" $1)

    for completion in $response; do
        IFS=',' read type value <<< "$completion"

        if [[ $type == 'dir' ]]; then
            COMPREPLY=()
            compopt -o dirnames
        elif [[ $type == 'file' ]]; then
            COMPREPLY=()
            compopt -o default
        elif [[ $type == 'plain' ]]; then
            COMPREPLY+=($value)
        fi
    done

    return 0
}

_git_twig_alias_completion() {
    if [ "${COMP_WORDS[1]}" = "twig" ]; then
        COMP_WORDS=("git-twig" ${COMP_WORDS[@]:2})
        COMP_CWORD=$((COMP_CWORD-1))

        _git_twig_completion git-twig
        return 0
    fi

    return 1
}

git-twig () {
    if [ "$1" = "switch" ] || ([ "$1" = "repository" ] && [ "$2" = "switch" ]); then
        dest=$(command git-twig $@)
        if [ $? -eq 0 ]; then
            echo "Switching to $dest"
            cd $dest
        fi
    else
        command git-twig $@
    fi
}

git (){
    if [ "$1" = "twig" ]; then
        shift 1
        git-twig $@
    else
        command git $@
    fi
}

complete -o nosort -F _git_twig_completion git-twig
complete -o nosort -F _git_twig_alias_completion git
