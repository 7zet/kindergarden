# Security Policy

## Qo'llab-quvvatlanadigan versiya

Xavfsizlik tuzatishlari faqat `main` branchning joriy versiyasiga beriladi.

## Zaiflik haqida xabar berish

Zaiflikni public issue sifatida ochmang. GitHub repository ichidagi
**Security → Report a vulnerability** orqali private security advisory yuboring.

Hisobotda ta'sir, qayta ishlab chiqarish qadamlari va mumkin bo'lsa minimal
proof-of-concept bo'lsin. Haqiqiy bolalar, ota-onalar, tokenlar, parollar yoki
database nusxalarini biriktirmang.

## Maxfiy ma'lumotlar

- `.env`, database dump, log, media va Telegram tokenlari commit qilinmaydi.
- Secret oshkor bo'lsa uni Git tarixidan o'chirishning o'zi yetmaydi — darhol
  credentialni almashtirish kerak.
- Production ma'lumotini test yoki issue ichiga ko'chirmang.

