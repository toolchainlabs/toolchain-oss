# Stores using constate

With usage of `@tanstack/react-query` there is little data we need to store so we use [constate](https://github.com/diegohaz/constate) a simple wrapper over the react context api. The stores cover mostly simple use cases of persistence. We test these using tests that render mostly a button and value. We test for mutability.