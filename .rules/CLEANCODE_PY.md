# Clean Code Python

## Core Principles

- **DRY** — Every piece of knowledge has a single, authoritative representation. Avoid duplication through abstraction,
  but don't over-abstract.
- **KISS** — Most systems work best when kept simple. Avoid unnecessary complexity.
- **SoC** — Divide programs into distinct sections addressing separate concerns (e.g., MVC). Only split when justified.
- **SOLID** — Single Responsibility, Open-Closed, Liskov Substitution, Interface Segregation, Dependency Inversion.

---

## Comments

> Code should explain itself. If you need a comment inside a method, rewrite the code instead.

**Rules:**

- No comments inside method bodies — name things so the code reads like prose
- Never comment out dead code — delete it; version control preserves history
- No noise comments that restate what the code already says
- Only docstrings are acceptable, and only at the function/class/module level

**Bad:**

```python
# This checks if the user with the given ID doesn't exist.
if not User.objects.filter(id=user_id).exists():
    return Response({'detail': 'User not found'})

numbers = [1, 2, 3, 4, 5]
# This variable stores the average of list of numbers.
average = sum(numbers) / len(numbers)
```

**Good:**

```python
if not User.objects.filter(id=user_id).exists():
    return Response({'detail': 'User not found'})

average = sum(numbers) / len(numbers)
```

**Acceptable docstring:**

```python
def model_to_dict(instance, fields=None, exclude=None):
    """
    Returns a dict containing the data in ``instance`` suitable for passing
    as a Form's ``initial`` keyword argument.

    ``fields`` is an optional list of field names. If provided, return only the named.
    ``exclude`` is an optional list of field names. If provided, exclude them from
    the returned dict, even if they are listed in the ``fields`` argument.
    """
```

---

## Naming

### Variables

Use nouns. Names must reveal intent without requiring context.

| Rule                  | Bad                                        | Good                                     |
|-----------------------|--------------------------------------------|------------------------------------------|
| Descriptive           | `c = 5`                                    | `city_counter = 5`                       |
| Pronounceable         | `genyyyymmddhhmmss = ...`                  | `generation_datetime = ...`              |
| No abbreviations      | `fna = 'Bob'`                              | `first_name = 'Bob'`                     |
| Consistent vocabulary | `client_first_name` + `customer_last_name` | `client_first_name` + `client_last_name` |
| No magic numbers      | `randint(0, 36)`                           | `randint(0, ROULETTE_POCKET_COUNT)`      |
| No redundant context  | `self.person_first_name` inside `Person`   | `self.first_name`                        |

**Include data type hints in names when helpful:**

```python
score_list = [12, 33, 14, 24]
word_dict = {'a': 'apple', 'b': 'banana'}
```

### Functions

Use verbs. The name must fully describe the action.

| Rule                   | Bad                             | Good                                        |
|------------------------|---------------------------------|---------------------------------------------|
| Consistent terminology | `get_name()` + `fetch_age()`    | `get_name()` + `get_age()`                  |
| Single responsibility  | `fetch_and_display_personnel()` | `fetch_personnel()` + `display_personnel()` |

If the function name contains "and", split it.

### Constants

```python
ROULETTE_POCKET_COUNT = 36
PI = 3.14159
```

### PEP 8 Conventions

| Kind                | Convention         | Example                      |
|---------------------|--------------------|------------------------------|
| Class               | `CamelCase`        | `MyClass`                    |
| Variable / Function | `snake_case`       | `first_name`, `quick_sort()` |
| Constant            | `UPPER_SNAKE_CASE` | `MAX_RETRIES`                |
| Module              | short lowercase    | `numpy`                      |

---

## Functions

### Keep functions small and single-purpose

Each function does one thing. If you can describe it without "and", it's probably right.

**Bad:**

```python
def fetch_and_display_personnel():
    data = ...
    for person in data:
        print(person)
```

**Good:**

```python
def fetch_personnel():
    return ...


def display_personnel(data):
    for person in data:
        print(person)
```

### Minimize arguments

Target one to two arguments. For more, encapsulate in a class.

**Bad:**

```python
def render_blog_post(title, author, created_timestamp, updated_timestamp, content):
    ...
```

**Good:**

```python
class BlogPost:
    def __init__(self, title, author, created_timestamp, updated_timestamp, content):
        self.title = title
        self.author = author
        self.created_timestamp = created_timestamp
        self.updated_timestamp = updated_timestamp
        self.content = content


def render_blog_post(blog_post):
    ...
```

### Avoid flag parameters

Boolean parameters indicate multiple responsibilities. Split instead.

**Bad:**

```python
def transform(text, uppercase):
    if uppercase:
        return text.upper()
    else:
        return text.lower()
```

**Good:**

```python
def uppercase(text):
    return text.upper()


def lowercase(text):
    return text.lower()
```

### Avoid side effects

Functions should not modify global state or external resources beyond their explicit output.

---

## Pythonic Code

Write code that uses Python idioms. Prefer built-ins and language features over manual implementations.

**Non-Pythonic:**

```python
n = 10
sum_all = 0
for i in range(1, n + 1):
    sum_all = sum_all + i
```

**Pythonic:**

```python
sum_all = sum(range(1, n + 1))
```

### Context Managers

Always use `with` for resource management — files, locks, database connections.

```python
with open('wisdom.txt', 'w') as opened_file:
    opened_file.write('Python is cool.')
```

### Generators over loading everything into memory

```python
def multiple_generator(x, n):
    for i in range(1, n + 1):
        yield x * i
```

### Decorators for cross-cutting concerns

```python
def require_passcode(func):
    def inner():
        passcode = input('Passcode: ')
        if passcode != '1234':
            print('Wrong passcode.')
            return
        func()

    return inner


@require_passcode
def start_server():
    print("Server started.")
```

---

## Formatting

- Two blank lines between top-level definitions
- One blank line between class methods
- One import per line
- No trailing whitespace
- Single space around binary operators; no spaces around `=` in keyword args

Enforce automatically with: **Black**, **Ruff**, or **Flake8**.

---

## Structure and Modularity

- Keep files under 200 lines when possible
- Apply OOP: encapsulation, abstraction, inheritance, polymorphism
- Split code into modules and packages by responsibility (SoC)
- Minimize interdependencies between modules

---

## Testing

Tests are production code. Write them. Untestable code is a signal that the design is wrong.

---

## The Zen of Python

```
import this
```

Key principles: explicit over implicit, simple over complex, readability counts, one obvious way to do it.