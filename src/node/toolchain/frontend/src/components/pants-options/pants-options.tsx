/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useEffect, useState, useMemo } from 'react';
import Grid from '@mui/material/Grid';
import TextField from '@mui/material/TextField';
import Snackbar from '@mui/material/Snackbar';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import IconButton from '@mui/material/IconButton';
import CloseIcon from '@mui/icons-material/Close';
import Chip from '@mui/material/Chip';
import FileCopyIcon from '@mui/icons-material/FileCopy';
import { Artifact } from 'common/interfaces/build-artifacts';
import ArtifactCard from 'pages/builds/artifact-card';
import { styled } from '@mui/material/styles';

const DataContainer = styled(Grid)(({ theme }) => ({
  backgroundColor: 'rgba(0, 169, 183, 0.08)',
  marginTop: theme.spacing(2),
  paddingLeft: theme.spacing(3),
  paddingRight: theme.spacing(3),
  paddingTop: 18,
  paddingBottom: theme.spacing(2),
  borderRadius: '8px',
}));

const CopyButton = styled(Chip)(({ theme }) => ({
  border: `1px solid rgba(0, 169, 183, 0.5)`,
  backgroundColor: 'transparemnt',
  borderRadius: '16px',
  marginLeft: theme.spacing(1),
  color: theme.palette.primary.main,
}));

const Arrow = styled('div')(({ theme }) => ({
  marginRight: theme.spacing(1),
}));

const NestedDataSubFolder = styled('div')(({ theme }) => ({
  marginLeft: theme.spacing(1.5),
  borderLeft: `1px solid rgba(0, 169, 183, 0.5)`,
  paddingLeft: theme.spacing(1),
}));

const NestedDataDots = styled('div')(({ theme }) => ({
  height: 12,
  borderTop: '1px dashed rgba(0, 169, 183, 0.5)',
  flex: 1,
  marginLeft: theme.spacing(1.5),
  alignSelf: 'flex-end',
}));

const ItemsCount = styled(Typography)(({ theme }) => ({
  marginLeft: theme.spacing(1),
}));

const ElementIndex = styled('div')(({ theme }) => ({
  color: theme.palette.primary.dark,
}));

const DisabledText = styled(Typography)(({ theme }) => ({
  color: theme.palette.text.disabled,
}));

const ColonContainer = styled('div')(({ theme }) => ({
  marginLeft: theme.spacing(2),
  marginRight: theme.spacing(1),
}));

const NestedDataLabel = styled('div')(() => ({
  display: 'flex',
  flexGrow: 1,
  alignItems: 'center',
  justifyContent: 'space-between',
  cursor: 'pointer',
}));

const LabelText = styled(Typography)(() => ({
  padding: '3px 0',
  display: 'flex',
}));

const DisabledLabelText = styled(LabelText)(({ theme }) => ({
  color: theme.palette.text.disabled,
}));

const FullDisplayValue = styled(Typography)(({ theme }) => ({
  color: theme.palette.secondary.main,
  padding: '3px 0',
}));

const Code = styled(Typography)(() => ({
  padding: '3px 0',
  display: 'flex',
}));

const CustomTextField = styled(TextField)(() => ({
  width: '100%',
  '& :after': {
    display: 'none',
  },
}));

type DataUnit = { value: any; searchParamPosition: number };
type BottomLevelFormatedData = { value: Array<DataUnit> | DataUnit; searchParamPosition: number };
type MidLevelFormatedData = { [key: string]: BottomLevelFormatedData };
type TopLevelFormatedData = { [key: string]: { value: MidLevelFormatedData; searchParamPosition: number } };

type PantsTableRowProps = {
  label?: string;
  numOfItems?: number;
  searchParamPosition?: number | null;
  matchLength?: number;
  value: any;
  elementIndex?: number;
  copyHandler?: (value: any) => any;
  isInitiallyOpened?: boolean;
  children?: React.ReactChild;
};

const PantsOptions = ({ artifact }: { artifact: Artifact<any> }) => {
  const [searchFilter, setSearchFilter] = useState<string>('');
  const [showCopyMessage, setShowCopyMessage] = useState<boolean>(false);

  const formatBottomLevelData: (data: any, searchParam: string) => DataUnit = (data, searchParam) => {
    const convertedData = typeof data === 'object' ? JSON.stringify(data) : data;
    const searchParamPosition = `${convertedData}`.indexOf(searchParam);
    return {
      searchParamPosition,
      value: data,
    };
  };

  const formatAllBottomLevelData: (data: any, searchParam: string) => DataUnit | DataUnit[] = (data, searchParam) => {
    if (Array.isArray(data)) {
      return data.map(el => formatBottomLevelData(el, searchParam)).filter(el => el.searchParamPosition >= 0);
    }

    return formatBottomLevelData(data, searchParam);
  };

  const formatFirstLevelData: (data: any, searchParam: string) => BottomLevelFormatedData = (data, searchParam) => {
    const myObj: any = {};
    Object.entries(data).forEach(([key, value]) => {
      const searchParamPosition = `${key}`.indexOf(searchParam);
      const nestedValue = formatAllBottomLevelData(value, searchParam);
      let hasChildThatMatchSearchFilter = false;

      if (Array.isArray(nestedValue)) {
        hasChildThatMatchSearchFilter = nestedValue.some(el => el.searchParamPosition >= 0);
      } else {
        hasChildThatMatchSearchFilter = nestedValue.searchParamPosition >= 0;
      }

      if (searchParamPosition >= 0 || hasChildThatMatchSearchFilter) {
        myObj[key] = {
          value: nestedValue,
          searchParamPosition,
        };
      }
    });

    if (Object.entries(myObj).length > 0) {
      return myObj;
    }

    return null;
  };

  const formatTopLevelData: (data: any, searchParam: string) => TopLevelFormatedData = (data, searchParam) => {
    if (!data) {
      return {};
    }

    const myObj: any = {};
    Object.entries(data).forEach(([key, value]) => {
      const searchParamPosition = `${key}`.indexOf(searchParam);
      const nestedValue = formatFirstLevelData(value, searchParam);
      if (searchParamPosition >= 0 || nestedValue) {
        myObj[key] = {
          value: nestedValue,
          searchParamPosition,
        };
      }
    });

    return myObj;
  };

  const getBottomLevelOriginalData = (formatedData: DataUnit | DataUnit[]) => {
    if (!formatedData) {
      return {};
    }

    if (Array.isArray(formatedData)) {
      return (formatedData as DataUnit[]).map(el => el.value);
    }

    return formatedData.value;
  };

  const getMidLevelOriginalData = (formatedData: MidLevelFormatedData) => {
    if (!formatedData) {
      return {};
    }

    const myObj: any = {};
    Object.entries(formatedData).forEach(([key, objValue]) => {
      myObj[key] = getBottomLevelOriginalData(objValue.value);
    });

    return myObj;
  };

  const getTopLevelOriginalData = (formatedData: TopLevelFormatedData) => {
    if (!formatedData) {
      return {};
    }

    const myObj: any = {};
    Object.entries(formatedData).forEach(([key, objValue]) => {
      myObj[key] = getMidLevelOriginalData(objValue.value);
    });

    return myObj;
  };

  const PantsTableRow = ({
    label,
    numOfItems = 0,
    searchParamPosition = null,
    matchLength = 0,
    value,
    elementIndex = -1,
    copyHandler = () => {},
    isInitiallyOpened = false,
    children,
  }: PantsTableRowProps) => {
    const [showChildren, setShowChildren] = useState<boolean>(true);
    const [showCopyButton, setShowCopyButton] = useState<boolean>(false);

    useEffect(() => {
      setShowChildren(isInitiallyOpened || matchLength > 0);
    }, [isInitiallyOpened, matchLength]);

    const onCopyHandler = (e: React.FormEvent<EventTarget>) => {
      e.stopPropagation();
      const originalData = copyHandler(value);
      const shouldStringify = typeof originalData === 'object';
      navigator.clipboard.writeText(shouldStringify ? JSON.stringify(originalData) : originalData);
      setShowCopyMessage(true);
    };

    const isValueArray = value && Array.isArray(value);
    let myValue = !isValueArray ? (value as DataUnit)?.value : null;
    myValue = myValue && typeof myValue === 'object' ? JSON.stringify(myValue) : myValue;
    const hasNestedElements = children || isValueArray;
    const longStringLimit = 40;
    const isLongString = myValue && typeof myValue === 'string' && myValue.length > longStringLimit;
    const numOfItemsString = `${numOfItems} item${numOfItems !== 1 ? 's' : ''}`;
    const isEmpty = hasNestedElements && numOfItems === 0;

    const displayArrayValue = () => {
      if (children || !value) {
        return null;
      }

      if (isValueArray) {
        return (
          <>
            {(value as DataUnit[]).map((el, index) => (
              <PantsTableRow
                key={el.value}
                value={el}
                elementIndex={index}
                copyHandler={getBottomLevelOriginalData}
                searchParamPosition={el.searchParamPosition}
                matchLength={matchLength}
              />
            ))}
          </>
        );
      }
      return null;
    };

    const displaySingleValue = () => {
      let content = null;
      const searchIndex = (value as DataUnit).searchParamPosition;

      const displayBoldedValue = (displayValue: string, isString: boolean) => {
        const codeColor = isString ? 'secondary.main' : 'primary.main';
        return searchIndex >= 0 ? (
          <>
            <Code variant="code1" color={codeColor}>
              {isString ? '"' : ''}
              {displayValue.substr(0, searchIndex)}
            </Code>
            <Code fontWeight="bold !important" variant="code1" color={codeColor}>
              {displayValue.substr(searchIndex, matchLength)}
            </Code>
            <Code variant="code1" color={codeColor}>
              {displayValue.substr(searchIndex + matchLength)}
              {isString ? '"' : ''}
            </Code>
          </>
        ) : (
          <FullDisplayValue variant="code1">
            {isString ? '"' : ''}
            {displayValue}
            {isString ? '"' : ''}
          </FullDisplayValue>
        );
      };

      if (typeof myValue === 'string') {
        const contractdText = isLongString ? `${myValue.substr(0, longStringLimit)}...` : myValue;
        content = displayBoldedValue(contractdText, true);
      } else {
        content = displayBoldedValue(`${myValue}`, false);
      }

      return (
        <>
          <ColonContainer>:</ColonContainer> {content}
        </>
      );
    };

    const TypographComponent = isEmpty ? DisabledLabelText : LabelText;

    return (
      <>
        <NestedDataLabel
          onClick={() => setShowChildren(prevState => !prevState)}
          onMouseEnter={() => setShowCopyButton(true)}
          onMouseLeave={() => setShowCopyButton(false)}
        >
          <Arrow>
            {isEmpty && <ChevronRightIcon color="disabled" />}
            {hasNestedElements && showChildren && !isEmpty ? <ExpandMoreIcon /> : null}
            {hasNestedElements && !showChildren && !isEmpty ? <ChevronRightIcon /> : null}
          </Arrow>

          {label && searchParamPosition >= 0 ? (
            <>
              <TypographComponent variant="body1">
                &quot;
                {label.substr(0, searchParamPosition)}
              </TypographComponent>
              <TypographComponent variant="body1" fontWeight="bold">
                {label.substr(searchParamPosition, matchLength)}
              </TypographComponent>
              <TypographComponent variant="body1">
                {label.substr(searchParamPosition + matchLength)}
                &quot;
              </TypographComponent>
            </>
          ) : null}
          {label && searchParamPosition < 0 && isEmpty && (
            <DisabledText variant="body1">
              &quot;
              {label}
              &quot;
            </DisabledText>
          )}
          {label && searchParamPosition < 0 && !isEmpty && (
            <Typography variant="body1">
              &quot;
              {label}
              &quot;
            </Typography>
          )}
          {elementIndex >= 0 && <ElementIndex>{elementIndex}</ElementIndex>}
          {!hasNestedElements && displaySingleValue()}
          {hasNestedElements && <ItemsCount variant="caption">{numOfItemsString}</ItemsCount>}
          <NestedDataDots />
          {showCopyButton && (
            <CopyButton
              variant="outlined"
              icon={<FileCopyIcon />}
              size="small"
              color="primary"
              label={isLongString ? 'Copy entire value' : 'Copy'}
              onClick={onCopyHandler}
            />
          )}
        </NestedDataLabel>
        {children && showChildren ? <NestedDataSubFolder>{children}</NestedDataSubFolder> : null}
        {hasNestedElements && showChildren ? displayArrayValue() : null}
      </>
    );
  };

  const createPantsOptionsTable = (formatedData: TopLevelFormatedData) => {
    if (!formatedData) {
      return null;
    }

    const formatedDataLength = Object.keys(formatedData).length;

    return (
      <PantsTableRow
        numOfItems={formatedDataLength}
        copyHandler={getTopLevelOriginalData}
        value={formatedData}
        isInitiallyOpened
      >
        <>
          {Object.entries(formatedData).map(([midKey, midValue]) => {
            const numOfItems = midValue?.value ? Object.keys(midValue.value).length : 0;
            return (
              <PantsTableRow
                label={midKey}
                key={midKey}
                searchParamPosition={midValue.searchParamPosition}
                matchLength={searchFilter.length}
                copyHandler={getMidLevelOriginalData}
                value={midValue.value}
                numOfItems={numOfItems}
                isInitiallyOpened
              >
                <>
                  {midValue.value &&
                    Object.entries(midValue.value).map(([nestedKey, nestedValue]) => {
                      const numOfNestedItems = Array.isArray(nestedValue.value) ? nestedValue.value.length : 0;
                      return (
                        <PantsTableRow
                          key={nestedKey}
                          label={nestedKey}
                          searchParamPosition={nestedValue.searchParamPosition}
                          matchLength={searchFilter.length}
                          value={nestedValue.value}
                          copyHandler={getBottomLevelOriginalData}
                          numOfItems={numOfNestedItems}
                        />
                      );
                    })}
                </>
              </PantsTableRow>
            );
          })}
        </>
      </PantsTableRow>
    );
  };

  const filteredData = formatTopLevelData(artifact.content, searchFilter);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const memoPantsOptionsTable = useMemo(() => createPantsOptionsTable(filteredData), [artifact.content, searchFilter]);

  return (
    <ArtifactCard hideAllHeaders>
      <Grid container direction="column">
        <Grid item>
          <form noValidate autoComplete="off">
            <CustomTextField
              label="Search options"
              id="search-files"
              color="secondary"
              onChange={e => setSearchFilter(e.target.value)}
              error={false}
            />
          </form>
        </Grid>
        <DataContainer item>{memoPantsOptionsTable}</DataContainer>
        <Snackbar
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
          autoHideDuration={5000}
          open={showCopyMessage}
          onClose={() => setShowCopyMessage(false)}
          message="Copied"
          action={
            <IconButton size="small" aria-label="close" color="inherit" onClick={() => setShowCopyMessage(false)}>
              <CloseIcon />
            </IconButton>
          }
        />
      </Grid>
    </ArtifactCard>
  );
};

export default PantsOptions;
