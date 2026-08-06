# This is based off of simpleSQL.py in the pyparsing github examples file.
from JoinGraphUtils import  *
from pyparsing import (
    Word,
    delimitedList,
    Optional,
    Group,
    alphas,
    alphanums,
    Forward,
    oneOf,
    QuotedString,
    infixNotation,
    opAssoc,
    restOfLine,
    CaselessKeyword,
    ParserElement,
    pyparsing_common as ppc,
    removeQuotes,
)

# Enable packrat parsing once at module level (memoization cache for backtracking)
ParserElement.enablePackrat()

# Forward declaration for recursive select-in-subquery references
_selectStmt = Forward()

# Build SQL grammar once at module level — reused across all parse calls
_SELECT, _FROM, _AS, _WHERE, _AND, _OR, _IN, _IS, _NOT, _NULL = map(
    CaselessKeyword, "SELECT FROM AS WHERE AND OR IN IS NOT NULL".split()
)
_NOT_NULL = _NOT + _NULL

_ident = Word(alphas, alphanums + "_$").setName("identifier")
_ident.addParseAction(ppc.upcaseTokens)
_aliasAndColumnName = delimitedList(_ident, '.')
_aliasAndColumnName.addParseAction(ppc.upcaseTokens)
_columnNameList = Group(delimitedList(_aliasAndColumnName).setName("column_list"))
_alias = Group(_ident + Optional(_AS + _ident))
_tableName = delimitedList(_alias, ",", combine=False).setName("table name")
_tableNameList = Group(delimitedList(_tableName).setName("table_list"))

_binop = oneOf("= != < > >= <= eq ne lt le gt ge LIKE", caseless=True).setName("binop")
_realNum = Group(ppc.real()).setResultsName("realNum")
_intNum = Group(ppc.signed_integer()).setResultsName('intNum')
_quoteStr = Group(QuotedString("'", unquoteResults=True))
_columnRval = (
    _realNum | _intNum | _quoteStr | _aliasAndColumnName
).setName("column_rvalue")

_whereCondition = Group(
    (_aliasAndColumnName + _binop + _columnRval)
    | (_aliasAndColumnName + _IN + Group("(" + delimitedList(_columnRval).setName("in_values_list") + ")"))
    | (_aliasAndColumnName + _IN + Group("[" + delimitedList(_columnRval).setName("in_values_list") + "]"))
    | (_aliasAndColumnName + _IN + Group("(" + _selectStmt + ")"))
    | (_aliasAndColumnName + _IS + (_NULL | _NOT_NULL))
    | (_aliasAndColumnName + Group(_NOT + _binop) + _columnRval)
).setName("where_condition")

_whereExpression = infixNotation(
    _whereCondition,
    [
        (_NOT, 1, opAssoc.RIGHT),
        (_AND, 2, opAssoc.LEFT),
        (_OR, 2, opAssoc.LEFT),
    ],
).setName("where_expression")

_selectStmt <<= (
    _SELECT
    + ("*" | _columnNameList)("columns")
    + _FROM
    + _tableNameList("tables")
    + Optional(Group(_WHERE + _whereExpression), "")("where")
).setName("select_statement")

_GRAMMAR = delimitedList(Group(_selectStmt), ";")

# ignore Oracle / MySQL comment styles
_oracleSqlComment = "--" + restOfLine
_GRAMMAR.ignore(_oracleSqlComment)
_mySQLComment = "#" + restOfLine
_GRAMMAR.ignore(_mySQLComment)


def getSQLGrammar():
    """Return the cached module-level SQL grammar (built once on import)."""
    return _GRAMMAR


def SQLQueriesToJoinQueryGraphs(sqlQuery, verbose=False):
    SQLGrammar = getSQLGrammar()
    joinQueryGraphs = []
    SQLParseResult = SQLGrammar.parseString(sqlQuery)
    counter = 0
    for queryParse in SQLParseResult:
        if verbose:
            print("Parsing Query: " + str(counter))
        counter += 1
        queryGraph = JoinQueryGraph()
        aliases = [(x[0], x[2]) for x in queryParse['tables'] if len(x) >1 and x[1] == "AS"]
        aliases += [(x[0], x[0]) for x in queryParse['tables'] if len(x) == 1]
        for alias in aliases:
            queryGraph.addAlias(alias[0], alias[1])
        whereClausesAndConjunctions = queryParse['where'][0][1]
        for clause in whereClausesAndConjunctions:
            isStr = isinstance(clause, str)
            isAnd = isStr and clause == 'AND'
            if not isStr or (isStr and not isAnd):
                if isStr and not isAnd:
                    clause = whereClausesAndConjunctions
                isJoin = (len(clause) == 5) and (clause[2] == "=")
                if isJoin:
                    queryGraph.addJoin(clause[0], clause[1], clause[3], clause[4])
                else:
                    predType = clause[2]
                    if clause[2][0] == "NOT":
                            predType = "NOT" + " " + str(clause[2][1])
                    if predType == 'IN':
                        if clause[3][1].getName() == 'intNum':
                            queryGraph.addPredicate(clause[0], clause[1], predType, [int(x[0]) for x in clause[3][1:-1]])
                        elif clause[3][1].getName() == 'realNum':
                            queryGraph.addPredicate(clause[0], clause[1], predType, [float(x[0]) for x in clause[3][1:-1]])
                        else:
                            queryGraph.addPredicate(clause[0], clause[1], predType, [str(x[0]) for x in clause[3][1:-1]])
                    elif predType.upper() == 'IS':
                        if clause[3] == "NOT":
                            queryGraph.addPredicate(clause[0], clause[1], "IS NOT NULL", None)
                        else:
                            queryGraph.addPredicate(clause[0], clause[1], "IS NULL", None)
                    elif clause[3].getName() == 'intNum':
                        queryGraph.addPredicate(clause[0], clause[1], predType, int(clause[3][0]))
                    elif clause[3].getName() == 'realNum':
                        queryGraph.addPredicate(clause[0], clause[1], predType, float(clause[3][0]))
                    else:
                        queryGraph.addPredicate(clause[0], clause[1], predType, str(clause[3][0]))
                if isStr and not isAnd:
                    break
        queryGraph.buildJoinGraph()
        joinQueryGraphs.append(queryGraph)
    return joinQueryGraphs


def SQLFileToJoinQueryGraphs(fileAddress, verbose=False):
    with open(fileAddress) as file:
        fileContents = file.read()
    return SQLQueriesToJoinQueryGraphs(fileContents, verbose)


def SQLFileToSQLStatements(fileAddress):
    with open(fileAddress) as file:
        fileContents = file.read()
    return fileContents.split(";")


def ResultsFileToSizes(fileAddress):
    with open(fileAddress) as file:
        fileContents = file.read()
    lines = fileContents.split("\n")
    sizes = []
    for line in lines:
        values = line.split("#")
        sizes.append(int(values[-1]))
    return sizes
