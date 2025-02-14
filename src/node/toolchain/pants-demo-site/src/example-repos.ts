/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import PantsbuildPants from './assets/pantsbuild_pants.png';
import DjangoDjango from './assets/django_django.png';
import EncodeDjango from './assets/encode_django-rest-framework.png';
import GetsentrySentry from './assets/getsentry_sentry.png';
import PalletsFlask from './assets/pallets_flask.png';
import PalletsJinja from './assets/pallets_jinja.png';
import PsfBlack from './assets/psf_black.png';
import PsfRequest from './assets/psf_requests.png';
import SimonwDatasettie from './assets/simonw_datasette.png';
import SqlalchemySqlalchemy from './assets/sqlalchemy_sqlalchemy.png';
import BackendAi from './assets/backend-ai.png';

type ExampleRepo = {
  organizationName: string;
  repoName: string;
  imgUrl?: string;
};

const exampleRepos: Array<ExampleRepo> = [
  {
    organizationName: 'pantsbuild',
    repoName: 'pants',
    imgUrl: PantsbuildPants,
  },
  {
    organizationName: 'django',
    repoName: 'django',
    imgUrl: DjangoDjango,
  },
  {
    organizationName: 'encode',
    repoName: 'django-rest-framework',
    imgUrl: EncodeDjango,
  },
  {
    organizationName: 'getsentry',
    repoName: 'sentry',
    imgUrl: GetsentrySentry,
  },
  {
    organizationName: 'pallets',
    repoName: 'flask',
    imgUrl: PalletsFlask,
  },
  {
    organizationName: 'pallets',
    repoName: 'jinja',
    imgUrl: PalletsJinja,
  },
  {
    organizationName: 'psf',
    repoName: 'black',
    imgUrl: PsfBlack,
  },
  {
    organizationName: 'psf',
    repoName: 'requests',
    imgUrl: PsfRequest,
  },
  {
    organizationName: 'simonw',
    repoName: 'datasette',
    imgUrl: SimonwDatasettie,
  },
  {
    organizationName: 'sqlalchemy',
    repoName: 'sqlalchemy',
    imgUrl: SqlalchemySqlalchemy,
  },
  {
    organizationName: 'lablup',
    repoName: 'backend.ai',
    imgUrl: BackendAi,
  },
];

export default exampleRepos;
