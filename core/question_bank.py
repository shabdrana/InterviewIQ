"""Offline question bank used when no LLM is available (clearly labelled 'bank' in the UI).
Each entry: category, domain, difficulty, text, expected key concepts (used for coverage checks)."""
from __future__ import annotations

B, I, A = "Beginner", "Intermediate", "Advanced"


def _q(cat, dom, diff, text, kws=(), exp=False):
    return {"category": cat, "domain": dom, "difficulty": diff, "text": text, "keywords": list(kws), "experienced": exp}


BANK = [
    # ---- HR
    _q("hr", None, B, "Tell me about yourself and what led you to apply for this role."),
    _q("hr", None, B, "Why are you interested in working for our company?"),
    _q("hr", None, B, "What are your greatest strengths, and how have they helped you in practice?"),
    _q("hr", None, I, "What is a weakness you are actively working on, and what have you done about it so far?"),
    _q("hr", None, I, "Where do you see yourself in five years, and how does this role fit that path?"),
    _q("hr", None, I, "How do you handle feedback that you disagree with?"),
    _q("hr", None, A, "Why should we hire you over other equally qualified candidates?"),
    _q("hr", None, I, "Why are you leaving your current role, and what are you looking for next?", exp=True),
    _q("hr", None, A, "What is your approach to negotiating scope or deadlines with a manager?", exp=True),
    # ---- Behavioral
    _q("behavioral", None, B, "Tell me about a time you worked in a team to finish a project. What was your contribution?"),
    _q("behavioral", None, B, "Describe a time you had to learn something new quickly."),
    _q("behavioral", None, I, "Tell me about a time you faced a tight deadline. How did you manage it?"),
    _q("behavioral", None, I, "Describe a conflict with a teammate and how you resolved it."),
    _q("behavioral", None, I, "Tell me about a time you made a mistake. What happened and what did you do next?"),
    _q("behavioral", None, A, "Describe a time you took initiative on something nobody asked you to do."),
    _q("behavioral", None, A, "Tell me about a time you had to influence a decision without having authority."),
    _q("behavioral", None, A, "Describe a project that failed or fell short. What would you change?", exp=True),
    _q("behavioral", None, A, "Tell me about a time you mentored or led others through a difficult task.", exp=True),
    # ---- General
    _q("general", None, B, "What motivates you to do your best work?"),
    _q("general", None, I, "How do you prioritise when several tasks are all urgent?"),
    _q("general", None, I, "What does a good engineering team culture look like to you?"),
    _q("general", None, A, "How do you keep your skills current in a field that changes this fast?"),
    # ---- Python
    _q("technical", "Python", B, "What is the difference between a list and a tuple in Python?",
       ["mutable", "immutable", "tuple", "list", "hashable", "performance"]),
    _q("technical", "Python", B, "What are Python decorators and when would you use one?",
       ["function", "wrapper", "decorator", "logging", "functools", "arguments"]),
    _q("technical", "Python", I, "Explain how Python manages memory, including garbage collection.",
       ["reference counting", "garbage collector", "cycle", "heap", "generation"]),
    _q("technical", "Python", I, "What is the Global Interpreter Lock and how does it affect concurrency?",
       ["GIL", "thread", "multiprocessing", "CPU-bound", "I/O-bound", "asyncio"]),
    _q("technical", "Python", A, "How do generators work, and when are they better than lists?",
       ["yield", "lazy", "iterator", "memory", "next", "stateful"]),
    # ---- C++
    _q("technical", "C++", B, "What is the difference between a pointer and a reference in C++?",
       ["pointer", "reference", "null", "reassign", "address", "alias"]),
    _q("technical", "C++", I, "Explain RAII and why it matters in C++.",
       ["resource", "constructor", "destructor", "scope", "smart pointer", "exception"]),
    _q("technical", "C++", I, "What is the difference between stack and heap allocation?",
       ["stack", "heap", "new", "delete", "lifetime", "automatic"]),
    _q("technical", "C++", A, "How do virtual functions work and what is a vtable?",
       ["virtual", "vtable", "polymorphism", "override", "dynamic dispatch", "base class"]),
    # ---- Java
    _q("technical", "Java", B, "What is the difference between an abstract class and an interface in Java?",
       ["abstract", "interface", "multiple inheritance", "default method", "implements", "extends"]),
    _q("technical", "Java", I, "How does HashMap work internally in Java?",
       ["hashCode", "equals", "bucket", "collision", "load factor", "resize"]),
    _q("technical", "Java", I, "Explain the difference between checked and unchecked exceptions.",
       ["checked", "unchecked", "RuntimeException", "throws", "compile", "handle"]),
    _q("technical", "Java", A, "How does garbage collection work in the JVM?",
       ["heap", "young generation", "old generation", "mark", "sweep", "GC"]),
    # ---- SQL
    _q("technical", "SQL", B, "What is the difference between WHERE and HAVING in SQL?",
       ["WHERE", "HAVING", "GROUP BY", "aggregate", "filter", "rows"]),
    _q("technical", "SQL", B, "Explain the different types of SQL joins.",
       ["inner join", "left join", "right join", "full join", "matching", "NULL"]),
    _q("technical", "SQL", I, "What is database normalisation and why is it used?",
       ["normal form", "redundancy", "1NF", "2NF", "3NF", "anomaly"]),
    _q("technical", "SQL", A, "How do indexes speed up queries, and what are their trade-offs?",
       ["index", "B-tree", "lookup", "write", "storage", "selectivity"]),
    # ---- DSA
    _q("technical", "DSA", B, "What is the difference between an array and a linked list?",
       ["array", "linked list", "contiguous", "insertion", "random access", "pointer"]),
    _q("technical", "DSA", I, "Explain how a hash table handles collisions.",
       ["hash function", "chaining", "open addressing", "collision", "load factor", "O(1)"]),
    _q("technical", "DSA", I, "When would you choose BFS over DFS?",
       ["BFS", "DFS", "shortest path", "queue", "stack", "level"]),
    _q("technical", "DSA", A, "Explain dynamic programming and how you recognise a DP problem.",
       ["overlapping subproblems", "optimal substructure", "memoization", "tabulation", "recurrence"]),
    _q("technical", "DSA", A, "Compare quicksort and mergesort in time, space and stability.",
       ["O(n log n)", "worst case", "pivot", "stable", "in-place", "extra space"]),
    # ---- AI/ML
    _q("technical", "AI/ML", B, "What is overfitting and how can you prevent it?",
       ["training", "validation", "regularization", "cross-validation", "more data", "dropout"]),
    _q("technical", "AI/ML", B, "Explain the difference between supervised and unsupervised learning.",
       ["labelled", "supervised", "unsupervised", "clustering", "classification", "regression"]),
    _q("technical", "AI/ML", I, "What is the bias-variance trade-off?",
       ["bias", "variance", "underfitting", "overfitting", "complexity", "generalisation"]),
    _q("technical", "AI/ML", I, "How do you evaluate a classification model on an imbalanced dataset?",
       ["precision", "recall", "F1", "ROC", "accuracy", "confusion matrix"]),
    _q("technical", "AI/ML", A, "Explain how backpropagation trains a neural network.",
       ["gradient", "chain rule", "loss", "weights", "learning rate", "forward pass"]),
    _q("technical", "AI/ML", A, "What is the attention mechanism in transformers and why does it matter?",
       ["query", "key", "value", "self-attention", "context", "parallel"]),
]
