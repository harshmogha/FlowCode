"""Sample algorithms shown in the Load dialog."""

EXAMPLES = [

    {
        "name": "Even or odd",
        "text": '''START
INPUT n : int "Enter a number"
IF n mod 2 = 0 THEN
    PRINT "Even"
ELSE
    PRINT "Odd"
END IF
END
''',
    },
    {
        "name": "Sum of 1 to n",
        "text": '''START
INPUT n : int "Enter n"
SET total = 0
FOR i FROM 1 TO n DO
    SET total = total + i
END FOR
PRINT "Sum is", total
END
''',
    },
    {
        "name": "Factorial (while loop)",
        "text": '''START
INPUT n : int "Enter a number"
SET result = 1
SET k = n
WHILE k > 1 DO
    SET result = result * k
    SET k = k - 1
END WHILE
PRINT "Factorial is", result
END
''',
    },
    {
        "name": "Quadratic equation",
        "text": '''START
INPUT a : float "Enter a"
INPUT b : float "Enter b"
INPUT c : float "Enter c"
SET d = b^2 - 4*a*c
IF d < 0 THEN
    PRINT "No real roots"
ELSE
    SET x1 = (-b + sqrt(d)) / (2*a)
    SET x2 = (-b - sqrt(d)) / (2*a)
    PRINT "Roots are", x1, x2
END IF
END
''',
    },
    {
        "name": "Bubble sort",
        "text": '''START
INPUT a : list "Enter numbers separated by spaces"
SET n = len(a)
FOR i FROM 0 TO n - 2 DO
    FOR j FROM 0 TO n - i - 2 DO
        IF a[j] > a[j + 1] THEN
            SET temp = a[j]
            SET a[j] = a[j + 1]
            SET a[j + 1] = temp
        END IF
    END FOR
END FOR
PRINT "Sorted:", a
END
''',
    },
    {
        "name": "Binary search",
        "text": '''START
INPUT a : list "Enter sorted numbers separated by spaces"
INPUT target : int "Enter number to find"
SET low = 0
SET high = len(a) - 1
SET pos = -1
WHILE low <= high DO
    SET mid = (low + high) div 2
    IF a[mid] = target THEN
        SET pos = mid
        SET low = high + 1
    ELSE IF a[mid] < target THEN
        SET low = mid + 1
    ELSE
        SET high = mid - 1
    END IF
END WHILE
IF pos = -1 THEN
    PRINT "Not found"
ELSE
    PRINT "Found at index", pos
END IF
END
''',
    },
    {
        "name": "Add two numbers (one line)",
        "text": '''START
INPUT a, b : int "Enter two numbers separated by a space"
PRINT "Sum is", a + b
END
''',
    },
    {
        "name": "Sum and average of many numbers",
        "text": '''START
INPUT nums : list "Enter any number of values separated by commas"
SET total = sum(nums)
SET count = len(nums)
PRINT "Sum is", total
PRINT "Average is", total / count
END
''',
    },
]
