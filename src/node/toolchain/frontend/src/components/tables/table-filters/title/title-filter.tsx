/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import Autocomplete from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';
import { useDebouncedCallback } from 'use-debounce';

import { useQueryGet } from 'utils/hooks/query';
import TitlesSuggestResponse from 'common/interfaces/title';
import QueryNames from 'common/enums/QueryNames';
import backends from 'utils/backend-paths';
import { useOrgAndRepoContext } from 'store/org-repo-store';

const MIN_TITLE_LENGTH = 3;
const SUGGEST_DELAY = 2000;
const TYPING_DELAY = 500;

type PullRequestTitleFilterProps = {
  fieldValue: string;
  onChange: (formField: { [key: string]: string | string[] }) => void;
  fieldName: string;
  fieldLabel: string;
};

const TitleFilter = ({ fieldValue, onChange, fieldName, fieldLabel }: PullRequestTitleFilterProps) => {
  const { repo, org } = useOrgAndRepoContext();
  const [titleResponse] = useQueryGet<TitlesSuggestResponse>(
    [`${repo}/${org}/${QueryNames.TITLE_SUGGEST}/${fieldValue}`],
    backends.buildsense_api.TITLE_SUGGEST(org, repo),
    { q: fieldValue },
    {
      enabled: !!fieldValue && fieldValue.trim().length >= MIN_TITLE_LENGTH,
      initialData: { values: [] },
    }
  );

  const updateQueryValue = (value: string) => {
    const val = value ? (value as string) : undefined;

    if (titleResponse.isFetching) {
      setTimeout(() => onChange({ [fieldName]: val }), SUGGEST_DELAY);
    } else {
      onChange({ [fieldName]: val });
    }
  };

  const debounced = useDebouncedCallback((value: string) => updateQueryValue(value), TYPING_DELAY);

  return (
    <Autocomplete
      freeSolo
      multiple={false}
      options={titleResponse?.data.values}
      value={fieldValue || null}
      onChange={(event, newValue) => updateQueryValue(newValue)}
      autoHighlight
      id={fieldName}
      renderInput={params => (
        <TextField
          // eslint-disable-next-line react/jsx-props-no-spreading
          {...params}
          label={fieldLabel}
          InputLabelProps={{ htmlFor: fieldName, id: fieldLabel }}
          margin="none"
          onChange={event => debounced(event.target.value)}
          name={fieldName}
        />
      )}
    />
  );
};

export default TitleFilter;
