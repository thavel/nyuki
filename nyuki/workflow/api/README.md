# Workflow history search

## `?ordering` values

|Value|Effect|
|-----|------|
|`title_asc`|Ascending sort on titles|
|`title_desc`|Descending sort on titles|
|`start_asc`|Ascending sort on start time|
|`start_desc`|Desending sort on start time|
|`end_asc`|Ascending sort on end time|
|`end_desc` (default)|Descending sort on end time|

## `?root` values

|Value|Effect|
|-----|------|
|`0` (default)|Show all workflows|
|`1`|Only show root workflows|

## `?full` values

|Value|Effect|
|-----|------|
|`0` (default)|Show only basic informations|
|`1`|Show the entire graphs and tasks exec|

## `?search=something-in-the-title`

## `?since=2016-12-12T15:36:58.983520`

Show all workflows since `12/12/2016 15:36:28.983520`.

## `?limit=10`

Limits the amount of workflows returned.

## `?offset=10`

Start from the 10th workflow returned.

## `?state` values

|Value|Effect|
|-----|------|
|`pending`|Show only pending workflows|
|`cancelled`|Show only cancelled workflows|
|`exception`|Show only crashed workflows due to exception|
|`finished`|Show only workflows that finished properly|
|`skipped`|Show only skipped workflows|
