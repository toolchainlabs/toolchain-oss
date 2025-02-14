/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { useEffect } from 'react';
import {
  useQuery as useReactQuery,
  useInfiniteQuery as useReactQueryInfinite,
  useMutation as useReactQueryMutation,
  QueryObserverOptions,
  InfiniteQueryObserverOptions,
  useQueryClient,
  InfiniteQueryObserverBaseResult,
  UseQueryResult,
  UseMutationResult,
  UseMutationOptions,
} from '@tanstack/react-query';
import { useCookies } from 'react-cookie';
import { captureException } from '@sentry/browser';

import { useAppVersionContext } from 'store/app-version-store';
import { getHost } from 'utils/init-data';
import RequestIdHeader from 'utils/constants';
import generateUrl from 'utils/url';
import getAccessToken, {
  getTokenTimeLeft,
  refreshAccessToken,
  getRefreshTokenCookieKey,
} from 'utils/hooks/access-token';
import { useRequestErrorContext } from 'store/request-error-store';
import { useServiceUnavailableContext } from 'store/service-unavailable-store';
import { baseConfig, formatErrorMessage, serviceUnavailable, getSleepTime, manualyHandledCodes } from 'utils/http';

const MAX_RETRY_TIME = 3;
let isRefreshingToken: boolean = false;
const waitForTimeOut = async (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export type HistoryAndRequestErrorProps = {
  error: unknown;
  retryProps: {
    status: number;
    setIsServiceUnavailable: (value: boolean) => void;
    reportToSentry: (error: unknown) => void;
    showRetrySnackbar: boolean;
  };
};

const commonConfig: QueryObserverOptions<any> = {
  retry: (failureCount, error) => {
    const { retryProps, error: err } = error as HistoryAndRequestErrorProps;
    const { status, setIsServiceUnavailable, reportToSentry, showRetrySnackbar } = retryProps;

    // If under MAX_RETRY_TIME attempts (or equal) and 503 || 502 retry
    if (failureCount <= MAX_RETRY_TIME && serviceUnavailable.errorCodes.includes(status)) {
      return true;
    } else if (failureCount > MAX_RETRY_TIME && serviceUnavailable.errorCodes.includes(status)) {
      reportToSentry(err);
      if (showRetrySnackbar) {
        setIsServiceUnavailable(true);
      }
      return false;
    }

    return false;
  },
  refetchOnWindowFocus: false,
};

const optionsConfig = {
  ...commonConfig,
  staleTime: 300000, // Value in miliseconds (5 min).
};

const getConfig: QueryObserverOptions<any> = {
  ...commonConfig,
};

function useQuery<T>(
  method: string,
  name: string[],
  path: string,
  queryFunction: Function,
  isInfiniteQuery: boolean,
  manualyHandleError: boolean,
  params?: { [key: string]: any },
  body?: string,
  queryConfig?: QueryObserverOptions<T> | InfiniteQueryObserverOptions<T> | UseMutationOptions<T>,
  showRetrySnackbar?: boolean
): [
  {
    errorMessage: string | null;
    abortQuery: (queryName: string[]) => void;
  } & Partial<InfiniteQueryObserverBaseResult<T>> &
    Partial<UseQueryResult<T>> &
    Partial<UseMutationResult<T>>
] {
  const { setServerAppVersion, setNoAppReload } = useAppVersionContext();
  const { errorMessage, setErrorMessage } = useRequestErrorContext();
  const { setIsServiceUnavailable } = useServiceUnavailableContext();
  const queryClient = useQueryClient();
  const [, , removeCookie] = useCookies();
  const makeQuery = async (pageParam: number | null): Promise<T> => {
    const accessToken = getAccessToken();
    const timeLeft = getTokenTimeLeft();
    const timeLimit = 40000;
    const shouldRefreshToken = timeLeft < timeLimit;
    if (shouldRefreshToken && accessToken) {
      if (!isRefreshingToken) {
        // Toggle isRefreshingToken and fetch token
        isRefreshingToken = true;
        await refreshAccessToken(() => removeCookie(getRefreshTokenCookieKey()));
        isRefreshingToken = false;
      } else {
        // Await for refreshing tokens to finish before making more requests
        for (let i = 0; i < 3; i += 1) {
          // eslint-disable-next-line
          await waitForTimeOut(getSleepTime());
          if (!isRefreshingToken) {
            break;
          }
        }
      }
    }

    const pageParamObject = isInfiniteQuery ? { page: pageParam } : {};
    const url = generateUrl(path, getHost(), { ...pageParamObject, ...params });
    const options: RequestInit = {
      ...baseConfig(),
      method,
      body,
    };

    const response = await fetch(url, options);
    const serverVersion = response.headers.get('X-SPA-Version');
    const requestId = response.headers.get(RequestIdHeader);

    const reportToSentry = (error: unknown) => {
      const sentryError = Object.keys(error).length ? new Error(JSON.stringify(error)) : new Error(error as string);

      captureException(sentryError, { tags: { requestUrl: path, requestId: requestId } });
    };

    if (serverVersion?.length) {
      const versionObj = JSON.parse(serverVersion);

      setServerAppVersion(versionObj.version);
      setNoAppReload(versionObj.no_reload);
    }

    try {
      const result: T = await response.json();

      if (!response.ok) {
        const errorDisplayMessage = formatErrorMessage(result);
        // Dont set global error for manually handled statuses/calls and service unavailable statuses
        if (
          !manualyHandledCodes.errorCodes.includes(response.status) &&
          !serviceUnavailable.errorCodes.includes(response.status) &&
          !manualyHandleError
        ) {
          reportToSentry(result);
          setErrorMessage(errorDisplayMessage);
        }

        // eslint-disable-next-line @typescript-eslint/return-await
        return Promise.reject({
          error: result,
          ...result,
          retryProps: {
            status: response.status,
            setIsServiceUnavailable,
            reportToSentry,
            showRetrySnackbar,
          },
        });
      }
      return result;
    } catch (error) {
      const err = formatErrorMessage(error);
      if (!manualyHandleError) {
        reportToSentry(error);
        setErrorMessage(err);
      }

      return Promise.reject({
        error: new Error(error as string),
        retryProps: {
          status: response.status,
          setIsServiceUnavailable,
          reportToSentry,
          showRetrySnackbar,
        },
      });
    }
  };
  const abortQuery = (queryName: string[]) => queryClient.cancelQueries(queryName);

  const { error, ...response } = queryFunction(name, ({ pageParam = 1 }) => makeQuery(pageParam), {
    ...queryConfig,
  });

  useEffect(() => {
    // Fail CanceledError python exception silently for now
    if (error && !typeof 'CancelledError') {
      setErrorMessage(formatErrorMessage(error));
    }
  }, [error, errorMessage, setErrorMessage]);

  return [{ ...response, errorMessage, abortQuery }];
}

export function useQueryGet<T>(
  name: string[],
  path: string,
  params?: { [key: string]: any },
  queryConfig?: QueryObserverOptions<T>,
  manualyHandleError = false,
  showRetrySnackbar = true
) {
  const isInfiniteQuery = false;
  const body: string = null;

  return useQuery<T>(
    'GET',
    name,
    path,
    useReactQuery,
    isInfiniteQuery,
    manualyHandleError,
    params,
    body,
    {
      ...getConfig,
      ...queryConfig,
    },
    showRetrySnackbar
  );
}

export function useQueryOptions<T>(
  name: string[],
  path: string,
  params?: { [key: string]: any },
  queryConfig?: QueryObserverOptions<T>,
  manualyHandleError = false
) {
  const isInfiniteQuery = false;
  const body: string = null;

  return useQuery<T>('OPTIONS', name, path, useReactQuery, isInfiniteQuery, manualyHandleError, params, body, {
    ...optionsConfig,
    ...queryConfig,
  });
}

export function useInfiniteQuery<T>(
  name: string[],
  path: string,
  params?: { [key: string]: any },
  queryConfig?: InfiniteQueryObserverOptions<T>,
  manualyHandleError = false
) {
  const isInfiniteQuery = true;
  const body: string = null;

  return useQuery<T>('GET', name, path, useReactQueryInfinite, isInfiniteQuery, manualyHandleError, params, body, {
    ...getConfig,
    ...queryConfig,
  });
}

export function useMutationPatch<T>(
  name: string[],
  path: string,
  body?: string,
  queryConfig?: UseMutationOptions<T>,
  manualyHandleError = false
) {
  const isInfiniteQuery = false;
  const params: null = null;

  return useQuery<T>('PATCH', name, path, useReactQueryMutation, isInfiniteQuery, manualyHandleError, params, body, {
    ...queryConfig,
  });
}

export function useMutationPost<T>(
  name: string[],
  path: string,
  body?: string,
  queryConfig?: UseMutationOptions<T>,
  manualyHandleError = false
) {
  const isInfiniteQuery = false;
  const params: null = null;

  return useQuery<T>('POST', name, path, useReactQueryMutation, isInfiniteQuery, manualyHandleError, params, body, {
    ...queryConfig,
  });
}

export function useMutationDelete<T>(
  name: string[],
  path: string,
  queryConfig?: UseMutationOptions<T>,
  manualyHandleError = false
) {
  const isInfiniteQuery = false;
  const params: null = null;
  const body: null = null;

  return useQuery<T>('DELETE', name, path, useReactQueryMutation, isInfiniteQuery, manualyHandleError, params, body, {
    ...queryConfig,
  });
}
