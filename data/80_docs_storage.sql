-- Supabase Storage docs 버킷 → 화면에서 문서 올리기·목록 보기 허용
-- Supabase 대시보드 > SQL Editor 에 통째로 붙여넣고 Run 을 누른다.
-- 다시 실행해도 오류가 나지 않는다 (버킷은 있으면 비공개로만 바꾸고, 허용 규칙은 지우고 새로 만든다).

-- 1. docs 버킷 만들기: 비공개(private) 버킷이라 docs.py 의 잠깐만 열리는 링크로만 내려받을 수 있다
--    이미 있으면 비공개로만 바꾼다 (예전에 공개로 만들었어도 비공개가 된다)
insert into storage.buckets (id, name, public)
values ('docs', 'docs', false)
on conflict (id) do update set public = false;

-- 2. 처음으로 되돌리기: 예전에 만든 허용 규칙이 있으면 지운다
drop policy if exists "docs 목록 보기" on storage.objects;
drop policy if exists "docs 올리기" on storage.objects;

-- 3. 허용 설정: 화면(anon·로그인 사용자)에서 docs 버킷에만 보기·올리기 가능
create policy "docs 목록 보기" on storage.objects
  for select to anon, authenticated
  using (bucket_id = 'docs');

create policy "docs 올리기" on storage.objects
  for insert to anon, authenticated
  with check (bucket_id = 'docs');

-- 4. 확인: "docs 목록 보기"(SELECT), "docs 올리기"(INSERT) 2줄이 나오면 성공
select policyname, cmd, roles
from pg_policies
where schemaname = 'storage'
  and tablename = 'objects'
  and policyname like 'docs %'
order by policyname;
