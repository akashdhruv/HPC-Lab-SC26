! kinds.F90 -- real and integer kinds used everywhere.
module kinds
   implicit none
   integer, parameter :: rk = selected_real_kind(15, 307)
   integer, parameter :: ik = selected_int_kind(18)
end module kinds
