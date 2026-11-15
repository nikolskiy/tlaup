------ MODULE AST -------
EXTENDS TLC
fairness == ""
 
ast == 
[type    |-> "multiprocess", 
 name  |-> "PcalProc", 
 decls |-> <<[var |-> "x", eqOrIn |-> "=", val |-> << "0" >>]>>,
 defs  |-> <<  >>,
 prcds |-> <<>>,
 procs |-> <<[name   |-> "p",
              fairness |-> "unfair", minusLabels |-> <<>>, plusLabels |-><<>>, proceduresCalled |-><<>>,
              eqOrIn |-> "\\in",
              id     |-> << "1", "..", "2" >>,
              decls  |-> <<>>,
              body   |-> <<[label |-> "A",
                            stmts |-> <<[type |-> "assignment",
                                         ass  |-> <<[lhs |-> [var |-> "x", sub |-> <<  >>],
                                                     rhs |-> << "x", "+", "1" >>]>>]>>]>>]>>]
==========================
