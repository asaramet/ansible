#!/usr/bin/env python3

def factorial(x):
    if x == 1:
        return 1

    return x * factorial(x-1)

num = 3
print("Factorial of ", num, " is:", factorial(num))