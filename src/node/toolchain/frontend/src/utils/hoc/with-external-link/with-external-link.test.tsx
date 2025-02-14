/*
Copyright 2020 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React from 'react';
import { screen } from '@testing-library/react';

import withExternalLink from './with-external-link';
import render from '../../../../tests/custom-render';

type TestComponentProps = { Icon?: React.FunctionComponent; text: string };
type RenderWithExternalLinkProps = {
  component: (props: TestComponentProps) => JSX.Element;
  icon: string;
  link: string;
  props: { text: string };
};

const defaultLink = 'www.google.com';
const defaultProps = { text: 'google link' };

const TestComponent = ({ Icon, text }: TestComponentProps) => (
  <>
    {Icon}
    <div>{text}</div>
  </>
);

const TestRenderWithExternalLink = ({ component, icon, link, props }: RenderWithExternalLinkProps) => {
  const Component = withExternalLink(component, link, icon);

  // eslint-disable-next-line react/jsx-props-no-spreading
  return <Component {...props} />;
};

describe('withExternalLink', () => {
  it('should render a link', () => {
    const { asFragment } = render(
      <TestRenderWithExternalLink component={TestComponent} icon={null} link={defaultLink} props={defaultProps} />
    );

    expect(asFragment()).toMatchSnapshot();
  });

  it('should render url prop as href of link', () => {
    const url = 'www.sample.com';
    render(<TestRenderWithExternalLink component={TestComponent} icon={null} link={url} props={defaultProps} />);

    const link = screen.getByText(/link/).closest('a');

    expect(link).toHaveAttribute('href', url);
  });

  it('should render text as link child', () => {
    const someLinkText = 'link to some site';
    render(
      <TestRenderWithExternalLink
        component={TestComponent}
        icon="seinfeld"
        link={defaultLink}
        props={{ text: someLinkText }}
      />
    );

    expect(screen.getByText(someLinkText)).toBeInTheDocument();
  });

  it('should render link with type external', () => {
    render(
      <TestRenderWithExternalLink component={TestComponent} icon={null} link={defaultLink} props={defaultProps} />
    );

    const link = screen.getByText(/link/).closest('a');

    expect(link).toHaveAttribute('type', 'external');
  });

  it('should render link with rel and target', () => {
    render(
      <TestRenderWithExternalLink component={TestComponent} icon={null} link={defaultLink} props={defaultProps} />
    );

    const link = screen.getByText(/link/).closest('a');

    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('should render github icon', () => {
    render(
      <TestRenderWithExternalLink component={TestComponent} icon="github" link={defaultLink} props={defaultProps} />
    );

    expect(screen.getByAltText('GitHub link icon')).toBeInTheDocument();
  });

  it('should render circle ci icon', () => {
    render(
      <TestRenderWithExternalLink component={TestComponent} icon="circleci" link={defaultLink} props={defaultProps} />
    );

    expect(screen.getByAltText('Circle ci link icon')).toBeInTheDocument();
  });

  it('should render travis ci icon', () => {
    render(
      <TestRenderWithExternalLink component={TestComponent} icon="travis-ci" link={defaultLink} props={defaultProps} />
    );

    expect(screen.getByAltText('Travis CI link icon')).toBeInTheDocument();
  });

  it('should render default icon', () => {
    render(
      <TestRenderWithExternalLink component={TestComponent} icon={null} link={defaultLink} props={defaultProps} />
    );

    expect(screen.getByAltText('External link icon')).toBeInTheDocument();
  });

  it('should render github icon', () => {
    render(
      <TestRenderWithExternalLink component={TestComponent} icon="bitbucket" link={defaultLink} props={defaultProps} />
    );

    expect(screen.getByAltText('Bitbucket link icon')).toBeInTheDocument();
  });

  it('should render buildkite icon', () => {
    render(
      <TestRenderWithExternalLink component={TestComponent} icon="buildkite" link={defaultLink} props={defaultProps} />
    );

    expect(screen.getByAltText('Buildkite link icon')).toBeInTheDocument();
  });

  it('should render jenkins icon', () => {
    render(
      <TestRenderWithExternalLink component={TestComponent} icon="jenkins" link={defaultLink} props={defaultProps} />
    );

    expect(screen.getByAltText('Jenkins link icon')).toBeInTheDocument();
  });
});
